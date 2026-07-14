# Thermalscape — street-level thermal comfort (SOLWEIG-GPU)

Meter-scale outdoor **UTCI** (Universal Thermal Climate Index) for Austin, computed
with [SOLWEIG-GPU](https://doi.org/10.21105/joss.09535) (Kamath et al., 2026, TExUS
Lab / Dev Niyogi) and draped on the 3D Cesium twin.

This upgrades the twin from tract-level *air* heat (CityForesight) to block-level
*felt* heat that accounts for 3D building geometry, shade, sky-view, and radiation.

## Pipeline (`scripts/build_tile.py`)

1. **OSM buildings** (Overpass) → `Building_DSM` / `DEM` / `Trees` rasters in UTM 32614.
2. **Open-Meteo** hourly → UMEP-format met forcing (temp, RH, pressure, shortwave, wind).
3. `solweig_gpu.thermal_comfort()` → per-hour UTCI GeoTIFF (auto-GPU, CPU fallback).
4. Colorize the mid-hour UTCI → `artifacts/utci.png` + `artifacts/utci.json` (WGS84 bounds).

## Run

```bash
conda install -n austwin -c conda-forge gdal   # osgeo bindings (one-time)
npm run thermal:build            # today, downtown tile   (~3 min CPU)
npm run thermal:build 2026-07-15 # a specific (hotter/clearer) day
npm run dev:thermal              # serve on :8013
```

Then in the web app: `/cityforesight` → 3D → **LIVE LAYERS → 🌡 UTCI**.

## API (`:8013`)

- `GET /health` — `{tile_available}`
- `GET /utci` — bounds, UTCI range (°C), date, PNG url
- `GET /utci.png` — the colorized tile

## Scale notes

- **GPU**: paper reports ~25–41× speedup (A6000). This CPU run did a 761×784 @ 1 m
  downtown tile, 3 hours, in ~164 s. City-scale = precompute many tiles offline (batch).
- **DSM**: MVP derives building heights from OSM (`height` / `building:levels`×3, else 6 m)
  on flat terrain. For fidelity, swap in a LiDAR-derived DSM + DEM and NLCD land cover.
- **Contrast** depends on the met forcing — clear, high-sun hours show strong sun/shade
  UTCI contrast; overcast hours look flat.
- Hourly met only (SOLWEIG constraint).
