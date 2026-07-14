"""Census tract boundaries and morphology features for Austin metro."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from app.config import settings
from app.data.census import fetch_tract_population, uniform_population_density
from app.data.nlcd import ensure_nlcd_clip, morphology_from_land_cover

logger = logging.getLogger(__name__)

# Texas cartographic tracts (500k) — Travis County filtered in code
TIGER_TRACTS_URL = "https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_48_tract_500k.zip"
TRAVIS_COUNTY_FIPS = "453"


def _fetch_travis_tracts_gdf() -> gpd.GeoDataFrame:
    """Load real Travis County census tract polygons from Census TIGER cartographic files."""
    gdf = gpd.read_file(TIGER_TRACTS_URL)
    gdf = gdf[gdf["COUNTYFP"] == TRAVIS_COUNTY_FIPS].copy()
    gdf = gdf.to_crs(4326)
    gdf["geometry"] = gdf.geometry.simplify(0.0003, preserve_topology=True)
    gdf["NAME"] = gdf["NAME"].apply(lambda n: f"Census Tract {n}" if n and not str(n).startswith("Census") else n)
    return gdf


def _build_morphology(gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    """Combine NLCD land cover zonal stats with Census population density."""
    aland = {row["GEOID"]: float(row["ALAND"]) for _, row in gdf.iterrows()}

    if settings.fetch_nlcd:
        try:
            raster_path = ensure_nlcd_clip()
            morph = morphology_from_land_cover(gdf, raster_path)
            logger.info("Computed NLCD morphology for %d tracts", len(morph))
        except Exception as exc:
            logger.warning("NLCD morphology fetch failed (%s); using land-area fallback", exc)
            morph = _fallback_morphology(gdf)
    else:
        logger.info("NLCD fetch disabled (CITYFORESIGHT_FETCH_NLCD=false)")
        morph = _fallback_morphology(gdf)

    pop_by_tract: dict[str, float] = {}
    if settings.census_api_key:
        try:
            acs_pop = fetch_tract_population(settings.census_api_key)
            for geoid, land_m2 in aland.items():
                pop = acs_pop.get(geoid)
                if pop and land_m2 > 0:
                    pop_by_tract[geoid] = pop / (land_m2 / 1_000_000.0)
        except Exception as exc:
            logger.warning("Census ACS fetch failed (%s); using area-weighted estimate", exc)

    if not pop_by_tract:
        pop_by_tract = uniform_population_density(aland)

    morph = morph.set_index("geoid")
    rows = []
    for _, row in gdf.iterrows():
        geoid = row["GEOID"]
        m = morph.loc[geoid] if geoid in morph.index else morph.iloc[0]
        rows.append(
            {
                "geoid": geoid,
                "name": row["NAME"],
                "impervious_ratio": float(m["impervious_ratio"]),
                "canopy_cover": float(m["canopy_cover"]),
                "drainage_capacity": float(m["drainage_capacity"]),
                "population_density": round(float(pop_by_tract.get(geoid, 0.0)), 1),
            }
        )
    return pd.DataFrame(rows)


def _fallback_morphology(gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    """Area- and centrality-based morphology when NLCD is unavailable."""
    import numpy as np

    center_lat, center_lon = 30.27, -97.74
    rows = []
    for _, row in gdf.iterrows():
        geoid = row["GEOID"]
        centroid = row.geometry.centroid
        urban = 1.0 - min(abs(centroid.y - center_lat) + abs(centroid.x - center_lon), 0.15) / 0.15
        impervious = float(np.clip(0.25 + 0.55 * urban, 0.15, 0.92))
        canopy = float(np.clip(0.45 - 0.35 * urban, 0.05, 0.65))
        drainage = float(np.clip(1.0 - impervious * 0.7, 0.1, 0.9))
        rows.append(
            {
                "geoid": geoid,
                "impervious_ratio": round(impervious, 4),
                "canopy_cover": round(canopy, 4),
                "drainage_capacity": round(drainage, 4),
            }
        )
    return pd.DataFrame(rows)


def fetch_tract_geojson(output_path: Path | None = None) -> dict:
    """Download Travis County census tract boundaries and morphology as GeoJSON."""
    output_path = output_path or settings.data_dir / "processed" / "tracts.geojson"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    gdf = _fetch_travis_tracts_gdf()
    morph = _build_morphology(gdf)
    morph_by_geoid = morph.set_index("geoid")

    features = []
    for _, row in gdf.iterrows():
        geoid = row["GEOID"]
        m = morph_by_geoid.loc[geoid]
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "GEOID": geoid,
                    "NAME": m["name"],
                    "impervious_ratio": m["impervious_ratio"],
                    "canopy_cover": m["canopy_cover"],
                    "drainage_capacity": m["drainage_capacity"],
                    "population_density": m["population_density"],
                },
                "geometry": row.geometry.__geo_interface__,
            }
        )

    geojson = {"type": "FeatureCollection", "features": features}
    output_path.write_text(json.dumps(geojson))
    morph_path = settings.data_dir / "processed" / "tract_morphology.csv"
    morph.to_csv(morph_path, index=False)
    return geojson


def load_tract_geojson(path: Path | None = None) -> dict:
    path = path or settings.data_dir / "processed" / "tracts.geojson"
    if not path.exists():
        return fetch_tract_geojson(path)
    return json.loads(path.read_text())


_tract_gdf_cache: gpd.GeoDataFrame | None = None


def _tract_gdf() -> gpd.GeoDataFrame:
    global _tract_gdf_cache
    if _tract_gdf_cache is None:
        geojson = load_tract_geojson()
        _tract_gdf_cache = gpd.GeoDataFrame.from_features(
            geojson["features"], crs="EPSG:4326"
        )
    return _tract_gdf_cache


def tract_at_point(lat: float, lon: float) -> dict | None:
    """Return tract properties for a lat/lon point, or None if outside coverage."""
    gdf = _tract_gdf()
    point = Point(lon, lat)
    matches = gdf[gdf.contains(point)]
    if matches.empty:
        return None
    row = matches.iloc[0]
    return {
        "geoid": row["GEOID"],
        "name": row.get("NAME", ""),
    }


def load_morphology_table(path: Path | None = None, *, rebuild: bool = False) -> pd.DataFrame:
    path = path or settings.data_dir / "processed" / "tract_morphology.csv"
    geojson = load_tract_geojson()
    n_tracts = len(geojson["features"])

    if path.exists() and not rebuild:
        df = pd.read_csv(path)
        if len(df) == n_tracts:
            return df

    rows = []
    for feat in geojson["features"]:
        props = feat["properties"]
        rows.append(
            {
                "geoid": props["GEOID"],
                "name": props.get("NAME", ""),
                "impervious_ratio": props["impervious_ratio"],
                "canopy_cover": props["canopy_cover"],
                "drainage_capacity": props["drainage_capacity"],
                "population_density": props["population_density"],
            }
        )
    df = pd.DataFrame(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return df


def tract_heat_adjustment(morph: pd.Series, base_hi: float) -> float:
    """Urban heat island adjustment from morphology (KIL grounding)."""
    imp = morph["impervious_ratio"]
    canopy = morph["canopy_cover"]
    drain = morph["drainage_capacity"]
    mean_imp = 0.52
    mean_canopy = 0.28
    delta = (
        6.5 * (imp - mean_imp)
        - 4.0 * (canopy - mean_canopy)
        - 1.5 * (drain - 0.55)
    )
    return float(base_hi + delta)
