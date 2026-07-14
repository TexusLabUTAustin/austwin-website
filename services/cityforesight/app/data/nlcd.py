"""NLCD 2021 land-cover zonal statistics for census tract morphology."""

from __future__ import annotations

import logging
import zipfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import geometry_mask
from rasterio.mask import mask
from shapely.geometry import box

from app.config import settings

logger = logging.getLogger(__name__)

NLCD_LAND_COVER_URL = (
    "https://edcftp.cr.usgs.gov/project/NLCD/dewitz/2021/"
    "nlcd_2021_land_cover_l48_20230630.zip"
)
# Travis County bounds (EPSG:4326) with small buffer
TRAVIS_BBOX = (-98.18, 30.02, -97.37, 30.63)

DEVELOPED_WEIGHTS: dict[int, float] = {21: 0.10, 22: 0.35, 23: 0.65, 24: 0.90}
FOREST_CLASSES = {41, 42, 43}
WATER_CLASSES = {11, 12}
WETLAND_CLASSES = {90, 95}


def _is_valid_zip(path: Path) -> bool:
    if not path.exists() or path.stat().st_size < 1_000_000:
        return False
    try:
        with zipfile.ZipFile(path) as zf:
            return zf.testzip() is None
    except (zipfile.BadZipFile, OSError):
        return False


def _download_file(url: str, dest: Path, *, max_retries: int = 5) -> None:
    import shutil
    import subprocess

    dest.parent.mkdir(parents=True, exist_ok=True)
    if _is_valid_zip(dest):
        logger.info("Using cached NLCD archive at %s", dest)
        return

    if shutil.which("curl"):
        logger.info("Downloading NLCD land cover via curl (resumable) → %s", dest)
        subprocess.run(
            [
                "curl",
                "-C",
                "-",
                "-L",
                "-f",
                "--retry",
                "10",
                "--retry-delay",
                "5",
                "-o",
                str(dest),
                url,
            ],
            check=True,
        )
        if _is_valid_zip(dest):
            logger.info("NLCD download complete (%d MB)", dest.stat().st_size // (1 << 20))
            return
        if dest.exists():
            dest.unlink()

    import requests

    chunk_size = 1 << 20
    for attempt in range(1, max_retries + 1):
        downloaded = dest.stat().st_size if dest.exists() else 0
        headers = {}
        mode = "ab" if downloaded else "wb"
        if downloaded:
            headers["Range"] = f"bytes={downloaded}-"
            logger.info(
                "Resuming NLCD download from %d MB (attempt %d/%d)",
                downloaded // (1 << 20),
                attempt,
                max_retries,
            )
        else:
            logger.info("Downloading NLCD land cover (~1.8 GB) — one-time fetch to %s", dest)

        try:
            with requests.get(url, stream=True, timeout=600, headers=headers) as resp:
                if downloaded and resp.status_code == 416:
                    if _is_valid_zip(dest):
                        return
                    dest.unlink()
                    continue
                resp.raise_for_status()
                total = downloaded + int(resp.headers.get("content-length", 0))
                with dest.open(mode) as fh:
                    for chunk in resp.iter_content(chunk_size=chunk_size):
                        if not chunk:
                            continue
                        fh.write(chunk)
                        downloaded += len(chunk)
                        if total and downloaded % (50 * chunk_size) < chunk_size:
                            pct = 100.0 * downloaded / total
                            logger.info("  NLCD download: %.1f%% (%d MB)", pct, downloaded // (1 << 20))
            if _is_valid_zip(dest):
                logger.info("NLCD download complete (%d MB)", dest.stat().st_size // (1 << 20))
                return
            logger.warning("Download finished but zip validation failed; retrying")
            dest.unlink()
        except (requests.exceptions.ChunkedEncodingError, requests.exceptions.ConnectionError, OSError) as exc:
            logger.warning("NLCD download interrupted (%s); will retry", exc)
            if attempt == max_retries:
                raise

    raise RuntimeError(f"Failed to download valid NLCD archive after {max_retries} attempts")


def _nlcd_vsi_path(zip_path: Path) -> str:
    with zipfile.ZipFile(zip_path) as zf:
        img_name = next(n for n in zf.namelist() if n.lower().endswith(".img"))
    return f"/vsizip/{zip_path}/{img_name}"


def _clip_raster_to_travis(vsi_path: str, clip_path: Path) -> Path:
    if clip_path.exists():
        return clip_path

    clip_path.parent.mkdir(parents=True, exist_ok=True)
    bbox = box(*TRAVIS_BBOX)
    logger.info("Clipping NLCD land cover to Travis County bbox → %s", clip_path)
    with rasterio.open(vsi_path) as src:
        gdf = gpd.GeoDataFrame(geometry=[bbox], crs="EPSG:4326").to_crs(src.crs)
        clipped, transform = mask(src, gdf.geometry, crop=True)
        meta = src.meta.copy()
        meta.update(
            {
                "height": clipped.shape[1],
                "width": clipped.shape[2],
                "transform": transform,
            }
        )
        with rasterio.open(clip_path, "w", **meta) as dst:
            dst.write(clipped)
    logger.info("NLCD clip saved (%d MB)", clip_path.stat().st_size // (1 << 20))
    return clip_path


def ensure_nlcd_clip() -> Path:
    """Return path to Travis-clipped NLCD 2021 land cover GeoTIFF."""
    clip_path = settings.data_dir / "processed" / "nlcd_landcover_travis.tif"
    if clip_path.exists():
        return clip_path

    raw_dir = settings.data_dir / "raw"
    zip_path = raw_dir / "nlcd_2021_land_cover_l48.zip"
    _download_file(NLCD_LAND_COVER_URL, zip_path)
    return _clip_raster_to_travis(_nlcd_vsi_path(zip_path), clip_path)


def morphology_from_land_cover(gdf: gpd.GeoDataFrame, raster_path: Path) -> pd.DataFrame:
    """Compute impervious, canopy, and drainage proxies from NLCD class counts per tract."""
    with rasterio.open(raster_path) as src:
        data = src.read(1)
        transform = src.transform
        gdf_proj = gdf.to_crs(src.crs)

    rows: list[dict[str, float | str]] = []
    for geoid, geom in zip(gdf["GEOID"], gdf_proj.geometry, strict=True):
        mask_arr = geometry_mask(
            [geom],
            out_shape=data.shape,
            transform=transform,
            invert=True,
            all_touched=True,
        )
        vals = data[mask_arr]
        vals = vals[vals > 0]
        if vals.size == 0:
            rows.append(
                {
                    "geoid": geoid,
                    "impervious_ratio": 0.5,
                    "canopy_cover": 0.25,
                    "drainage_capacity": 0.5,
                }
            )
            continue

        total_px = float(vals.size)
        counts: dict[int, int] = {}
        for class_id in np.unique(vals):
            counts[int(class_id)] = int(np.sum(vals == class_id))

        weighted_imp = sum(counts.get(c, 0) * w for c, w in DEVELOPED_WEIGHTS.items())
        forest_px = sum(counts.get(c, 0) for c in FOREST_CLASSES)
        water_px = sum(counts.get(c, 0) for c in WATER_CLASSES)
        wetland_px = sum(counts.get(c, 0) for c in WETLAND_CLASSES)

        impervious = float(np.clip(weighted_imp / total_px, 0.05, 0.95))
        canopy = float(np.clip(forest_px / total_px, 0.02, 0.85))
        drainage = float(
            np.clip((water_px + wetland_px) / total_px + (1.0 - impervious) * 0.15, 0.08, 0.92)
        )
        rows.append(
            {
                "geoid": geoid,
                "impervious_ratio": round(impervious, 4),
                "canopy_cover": round(canopy, 4),
                "drainage_capacity": round(drainage, 4),
            }
        )

    return pd.DataFrame(rows)
