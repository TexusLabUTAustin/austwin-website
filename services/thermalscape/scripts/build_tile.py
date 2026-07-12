"""Precompute a street-level UTCI (thermal comfort) tile for Austin with SOLWEIG-GPU.

Pipeline:
  1. OSM buildings (Overpass) -> Building_DSM / DEM / Trees rasters in UTM 32614
  2. Open-Meteo hourly -> UMEP-format meteorological forcing file
  3. solweig_gpu.thermal_comfort() -> UTCI GeoTIFF (per hour)
  4. Colorize UTCI -> PNG + WGS84 bounds JSON for the Cesium overlay

Runs on CPU (slow) or GPU (auto). Start small: a compact downtown tile.
Usage: python build_tile.py [YYYY-MM-DD]
"""

from __future__ import annotations

import glob
import json
import os
import shutil
import sys
from datetime import date, datetime

import numpy as np
import rasterio
import requests
from PIL import Image
from pyproj import Transformer
from rasterio.features import rasterize
from rasterio.transform import from_origin
from shapely.geometry import shape
from shapely.ops import transform as shp_transform

# --- Tile config: compact downtown Austin block (keep small for CPU) ---
WEST, SOUTH, EAST, NORTH = -97.7460, 30.2640, -97.7380, 30.2710
RES_M = 1.0                       # raster resolution (meters)
UTM = "EPSG:32614"                # Austin UTM zone
DEFAULT_BUILDING_H = 6.0          # fallback building height (m)
HOURS = (13, 14, 15)             # daytime hours to simulate (local)

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(HERE, "work")
ART = os.path.join(HERE, "artifacts")
os.makedirs(WORK, exist_ok=True)
os.makedirs(ART, exist_ok=True)


def fetch_buildings() -> list[tuple[object, float]]:
    """Overpass -> list of (shapely polygon in WGS84, height meters)."""
    q = (
        f'[out:json][timeout:90];way["building"]({SOUTH},{WEST},{NORTH},{EAST});out geom;'
    )
    endpoints = [
        "https://overpass.kumi.systems/api/interpreter",
        "https://overpass-api.de/api/interpreter",
        "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    ]
    last = None
    els = None
    for url in endpoints:
        try:
            r = requests.post(
                url, data={"data": q},
                headers={"User-Agent": "AusTwin-Thermalscape/0.1 (contact@austwin.org)"},
                timeout=120,
            )
            r.raise_for_status()
            els = r.json().get("elements", [])
            break
        except Exception as e:  # noqa: BLE001
            last = e
            print(f"  Overpass {url} failed ({e}); trying next…")
    if els is None:
        raise SystemExit(f"All Overpass endpoints failed: {last}")
    polys: list[tuple[object, float]] = []
    for el in els:
        geom = el.get("geometry")
        if not geom or len(geom) < 3:
            continue
        coords = [(p["lon"], p["lat"]) for p in geom]
        if coords[0] != coords[-1]:
            coords.append(coords[0])
        tags = el.get("tags", {})
        h = _height(tags)
        polys.append((shape({"type": "Polygon", "coordinates": [coords]}), h))
    return polys


def _height(tags: dict) -> float:
    raw = tags.get("height")
    if raw:
        try:
            return float(str(raw).split()[0].replace("m", ""))
        except ValueError:
            pass
    lv = tags.get("building:levels")
    if lv:
        try:
            return float(lv) * 3.0
        except ValueError:
            pass
    return DEFAULT_BUILDING_H


def build_rasters() -> tuple[str, str, str]:
    print("Fetching OSM buildings…")
    polys = fetch_buildings()
    print(f"  {len(polys)} buildings")

    to_utm = Transformer.from_crs("EPSG:4326", UTM, always_xy=True).transform
    minx, miny = to_utm(WEST, SOUTH)
    maxx, maxy = to_utm(EAST, NORTH)
    width = int((maxx - minx) / RES_M)
    height = int((maxy - miny) / RES_M)
    transform = from_origin(minx, maxy, RES_M, RES_M)
    print(f"  grid {width}x{height} @ {RES_M}m, UTM bounds {minx:.0f},{miny:.0f} - {maxx:.0f},{maxy:.0f}")

    shapes = []
    for poly, h in polys:
        shapes.append((shp_transform(to_utm, poly), float(h)))
    heights = (
        rasterize(shapes, out_shape=(height, width), transform=transform, fill=0.0, dtype="float32")
        if shapes
        else np.zeros((height, width), dtype="float32")
    )

    dem = np.zeros((height, width), dtype="float32")          # flat terrain baseline
    trees = np.zeros((height, width), dtype="float32")        # no vegetation DSM (MVP)
    building_dsm = dem + heights                              # terrain + building height

    meta = dict(
        driver="GTiff", dtype="float32", count=1, width=width, height=height,
        crs=UTM, transform=transform, nodata=None,
    )
    paths = {}
    for name, arr in (("Building_DSM", building_dsm), ("DEM", dem), ("Trees", trees)):
        p = os.path.join(WORK, f"{name}.tif")
        with rasterio.open(p, "w", **meta) as dst:
            dst.write(arr, 1)
        paths[name] = p
    print("  wrote rasters:", ", ".join(paths.values()))
    return paths["Building_DSM"], paths["DEM"], paths["Trees"]


def build_metfile(day: str) -> str:
    """UMEP-format met forcing from Open-Meteo for the given date + HOURS."""
    clon, clat = (WEST + EAST) / 2, (SOUTH + NORTH) / 2
    r = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": clat, "longitude": clon,
            "hourly": "temperature_2m,relative_humidity_2m,surface_pressure,shortwave_radiation,wind_speed_10m",
            "wind_speed_unit": "ms", "timezone": "America/Chicago",
            "start_date": day, "end_date": day,
        },
        timeout=60,
    )
    r.raise_for_status()
    h = r.json()["hourly"]
    doy = datetime.strptime(day, "%Y-%m-%d").timetuple().tm_yday
    yr = datetime.strptime(day, "%Y-%m-%d").year

    cols = ["iy", "id", "it", "imin", "Q*", "QH", "QE", "Qs", "Qf", "Wind", "RH", "Td",
            "press", "rain", "Kdn", "snow", "ldown", "fcld", "wuh", "xsmd", "lai_hr",
            "Kdiff", "Kdir", "Wd"]
    rows = []
    for i, t in enumerate(h["time"]):
        hour = int(t[11:13])
        if hour not in HOURS:
            continue
        rows.append([
            yr, doy, hour, 0,
            -999, -999, -999, -999, -999,
            round(h["wind_speed_10m"][i], 2),
            round(h["relative_humidity_2m"][i], 1),
            round(h["temperature_2m"][i], 2),
            round(h["surface_pressure"][i] / 10.0, 3),   # hPa -> kPa
            0,
            round(h["shortwave_radiation"][i], 1),
            -999, -999, -999, -999, -999, -999, -999, -999, -999,
        ])
    if not rows:
        raise SystemExit("No met rows for requested hours (future date? Open-Meteo range).")
    path = os.path.join(WORK, "metforcing.txt")
    with open(path, "w") as f:
        f.write(" ".join(cols) + "\n")
        for row in rows:
            f.write(" ".join(str(x) for x in row) + "\n")
    print(f"  met file: {path} ({len(rows)} hours)")
    return path


def run_solweig(bdsm: str, dem: str, trees: str, met: str, day: str) -> None:
    from solweig_gpu import thermal_comfort

    print("Running SOLWEIG-GPU (this can take minutes on CPU)…")
    thermal_comfort(
        base_path=WORK,
        selected_date_str=day,
        building_dsm_filename=bdsm,
        dem_filename=dem,
        trees_filename=trees,
        landcover_filename=None,
        tile_size=4000,
        use_own_met=True,
        own_met_file=met,
        save_tmrt=True,
    )


def export_png(day: str) -> None:
    tifs = sorted(glob.glob(os.path.join(WORK, "**", "*UTCI*.tif"), recursive=True))
    if not tifs:
        tifs = sorted(glob.glob(os.path.join(WORK, "**", "*utci*.tif"), recursive=True))
    if not tifs:
        raise SystemExit(f"No UTCI output found under {WORK}")
    src_path = tifs[len(tifs) // 2]  # middle hour
    print("Colorizing", src_path)
    with rasterio.open(src_path) as src:
        data = src.read(1).astype("float32")
        b = src.bounds
        to_wgs = Transformer.from_crs(src.crs, "EPSG:4326", always_xy=True).transform
        west, south = to_wgs(b.left, b.bottom)
        east, north = to_wgs(b.right, b.top)

    valid = np.isfinite(data) & (data > -100)
    lo, hi = np.percentile(data[valid], [2, 98]) if valid.any() else (20, 46)
    rgba = _utci_colormap(data, lo, hi, valid)
    img = Image.fromarray(rgba, "RGBA")
    img.save(os.path.join(ART, "utci.png"))
    art_tif = os.path.join(ART, "utci.tif")
    shutil.copy2(src_path, art_tif)
    mean_c = float(np.mean(data[valid])) if valid.any() else float(lo)
    flat_idx_max = int(np.argmax(np.where(valid, data, -999)))
    flat_idx_min = int(np.argmin(np.where(valid, data, 999)))
    h, w = data.shape
    max_r, max_c = divmod(flat_idx_max, w)
    min_r, min_c = divmod(flat_idx_min, w)
    lon_span = east - west
    lat_span = north - south

    def cell_center(row: int, col: int) -> tuple[float, float]:
        lon = west + (col + 0.5) / w * lon_span
        lat = north - (row + 0.5) / h * lat_span
        return lat, lon

    hot_lat, hot_lon = cell_center(max_r, max_c)
    cool_lat, cool_lon = cell_center(min_r, min_c)
    meta = {
        "bounds": {"west": west, "south": south, "east": east, "north": north},
        "range_c": [float(lo), float(hi)],
        "mean_c": round(mean_c, 2),
        "spread_c": round(float(data[max_r, max_c] - data[min_r, min_c]), 2),
        "hotspot": {
            "lat": hot_lat,
            "lon": hot_lon,
            "utci_c": float(data[max_r, max_c]),
        },
        "coolest": {
            "lat": cool_lat,
            "lon": cool_lon,
            "utci_c": float(data[min_r, min_c]),
        },
        "date": day, "hours": list(HOURS), "source": os.path.basename(src_path),
        "generated_utc": datetime.utcnow().isoformat() + "Z",
    }
    with open(os.path.join(ART, "utci.json"), "w") as f:
        json.dump(meta, f, indent=2)
    print("Wrote", os.path.join(ART, "utci.png"), "and utci.json")
    print("bounds:", meta["bounds"], "range_c:", meta["range_c"])


def _utci_colormap(data, lo, hi, valid):
    """UTCI thermal-stress ramp: blue(cold)->green->yellow->red(heat stress)."""
    stops = [(0.0, (43, 131, 186)), (0.35, (120, 198, 163)), (0.5, (255, 255, 191)),
             (0.7, (253, 174, 97)), (1.0, (215, 25, 28))]
    t = np.clip((data - lo) / max(hi - lo, 1e-3), 0, 1)
    rgba = np.zeros((*data.shape, 4), dtype="uint8")
    for c in range(3):
        xs = [s[0] for s in stops]
        ys = [s[1][c] for s in stops]
        rgba[..., c] = np.interp(t, xs, ys).astype("uint8")
    rgba[..., 3] = np.where(valid, 205, 0).astype("uint8")
    return rgba


def main() -> None:
    day = sys.argv[1] if len(sys.argv) > 1 else date.today().isoformat()
    print(f"=== Thermalscape UTCI tile for {day} ===")
    bdsm, dem, trees = build_rasters()
    met = build_metfile(day)
    run_solweig(bdsm, dem, trees, met, day)
    export_png(day)
    print("Done.")


if __name__ == "__main__":
    main()
