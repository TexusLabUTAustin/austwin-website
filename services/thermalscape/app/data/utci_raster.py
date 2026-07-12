"""Load UTCI raster for sampling and summary stats."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np

from app.config import settings

ART = settings.artifacts_dir
_SERVICE_ROOT = Path(__file__).resolve().parents[2]
META_PATH = ART / "utci.json"
TIF_CANDIDATES = [
    ART / "utci.tif",
    _SERVICE_ROOT / "work/output_folder/0_0/UTCI_0_0.tif",
]


def _find_tif() -> Path | None:
    for p in TIF_CANDIDATES:
        if p.exists():
            return p
    return None


@lru_cache(maxsize=1)
def _load_raster() -> tuple[np.ndarray, dict] | None:
    import rasterio
    from pyproj import Transformer

    tif = _find_tif()
    if tif is None:
        return None
    with rasterio.open(tif) as src:
        data = src.read(1).astype("float32")
        b = src.bounds
        to_wgs = Transformer.from_crs(src.crs, "EPSG:4326", always_xy=True).transform
        west, south = to_wgs(b.left, b.bottom)
        east, north = to_wgs(b.right, b.top)
        meta = {
            "bounds": {"west": west, "south": south, "east": east, "north": north},
            "width": src.width,
            "height": src.height,
            "crs": str(src.crs),
        }
    return data, meta


def load_meta() -> dict:
    if META_PATH.exists():
        return json.loads(META_PATH.read_text())
    loaded = _load_raster()
    if not loaded:
        return {}
    _, raster_meta = loaded
    return {"bounds": raster_meta["bounds"]}


def _in_bounds(lat: float, lon: float, bounds: dict) -> bool:
    return (
        bounds["west"] <= lon <= bounds["east"]
        and bounds["south"] <= lat <= bounds["north"]
    )


def utci_stress_category(value_c: float) -> str:
    if value_c < 26:
        return "no_stress"
    if value_c < 32:
        return "moderate"
    if value_c < 38:
        return "strong"
    if value_c < 46:
        return "very_strong"
    return "extreme"


def utci_stress_label(value_c: float) -> str:
    return {
        "no_stress": "No thermal stress",
        "moderate": "Moderate heat stress",
        "strong": "Strong heat stress",
        "very_strong": "Very strong heat stress",
        "extreme": "Extreme heat stress",
    }[utci_stress_category(value_c)]


def compute_summary(data: np.ndarray, raster_meta: dict) -> dict:
    valid = np.isfinite(data) & (data > -100)
    if not valid.any():
        return {}
    vals = data[valid]
    lo = float(np.percentile(vals, 2))
    hi = float(np.percentile(vals, 98))
    mean = float(np.mean(vals))
    flat_idx_max = int(np.argmax(np.where(valid, data, -999)))
    flat_idx_min = int(np.argmin(np.where(valid, data, 999)))
    h, w = data.shape
    max_r, max_c = divmod(flat_idx_max, w)
    min_r, min_c = divmod(flat_idx_min, w)

    bounds = raster_meta["bounds"]
    lon_span = bounds["east"] - bounds["west"]
    lat_span = bounds["north"] - bounds["south"]

    def cell_center(row: int, col: int) -> tuple[float, float]:
        lon = bounds["west"] + (col + 0.5) / w * lon_span
        lat = bounds["north"] - (row + 0.5) / h * lat_span
        return lat, lon

    hot_lat, hot_lon = cell_center(max_r, max_c)
    cool_lat, cool_lon = cell_center(min_r, min_c)

    return {
        "range_c": [lo, hi],
        "mean_c": round(mean, 2),
        "hotspot": {
            "lat": hot_lat,
            "lon": hot_lon,
            "utci_c": float(data[max_r, max_c]),
            "label": utci_stress_label(float(data[max_r, max_c])),
        },
        "coolest": {
            "lat": cool_lat,
            "lon": cool_lon,
            "utci_c": float(data[min_r, min_c]),
            "label": utci_stress_label(float(data[min_r, min_c])),
        },
        "spread_c": round(float(data[max_r, max_c] - data[min_r, min_c]), 2),
    }


def sample_at(lat: float, lon: float) -> dict | None:
    loaded = _load_raster()
    meta = load_meta()
    bounds = meta.get("bounds") or (loaded[1]["bounds"] if loaded else None)
    if not bounds or not _in_bounds(lat, lon, bounds):
        return None
    if not loaded:
        return None
    data, raster_meta = loaded
    h, w = data.shape
    b = bounds
    col = int((lon - b["west"]) / (b["east"] - b["west"]) * w)
    row = int((b["north"] - lat) / (b["north"] - b["south"]) * h)
    col = max(0, min(w - 1, col))
    row = max(0, min(h - 1, row))
    value = float(data[row, col])
    if not np.isfinite(value) or value <= -100:
        return None
    lo, hi = meta.get("range_c", [None, None])
    if lo is None or hi is None:
        summary = compute_summary(data, raster_meta)
        lo, hi = summary.get("range_c", [value, value])
    return {
        "lat": lat,
        "lon": lon,
        "utci_c": round(value, 1),
        "stress": utci_stress_category(value),
        "stress_label": utci_stress_label(value),
        "range_c": [lo, hi],
        "normalized": float(np.clip((value - lo) / max(hi - lo, 1e-3), 0, 1)),
    }


def full_payload() -> dict:
    meta = load_meta()
    loaded = _load_raster()
    if loaded:
        data, raster_meta = loaded
        summary = compute_summary(data, raster_meta)
        meta = {**meta, **summary}
        if "range_c" not in meta and summary.get("range_c"):
            meta["range_c"] = summary["range_c"]
    meta["png_url"] = "/api/thermal/utci.png"
    meta["sample_available"] = loaded is not None
    meta["stress_scale"] = [
        {"max_c": 26, "label": "No stress", "color": "#78c6a3"},
        {"max_c": 32, "label": "Moderate", "color": "#fff3bf"},
        {"max_c": 38, "label": "Strong", "color": "#fdae61"},
        {"max_c": 46, "label": "Very strong", "color": "#f46d43"},
        {"max_c": 999, "label": "Extreme", "color": "#d73027"},
    ]
    return meta
