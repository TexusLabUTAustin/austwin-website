#!/usr/bin/env python3
"""Fetch ASOS weather, tract boundaries, and morphology features."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.data.asos import fetch_asos
from app.data.tracts import fetch_tract_geojson, load_morphology_table

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch CityForesight training data")
    parser.add_argument(
        "--skip-nlcd",
        action="store_true",
        help="Skip NLCD land-cover download (~1.8 GB); uses centroid fallback for morphology",
    )
    parser.add_argument(
        "--asos-only",
        action="store_true",
        help="Refresh ASOS weather only (skip tract/morphology)",
    )
    args = parser.parse_args()

    if args.skip_nlcd:
        settings.fetch_nlcd = False

    print("Fetching ASOS hourly data for KAUS (2018–2024)...")
    asos_path = settings.data_dir / "processed" / "asos_hourly.csv"
    df = fetch_asos(station=settings.station_id, year1=2018, year2=2024, output_path=asos_path)
    print(f"  → {len(df)} hourly records saved to {asos_path}")

    if args.asos_only:
        print("Done (ASOS only).")
        return

    if settings.fetch_nlcd:
        print("Fetching Travis County census tracts + NLCD 2021 land cover morphology...")
        print("  (First run downloads ~1.8 GB NLCD raster; cached under data/raw/)")
    else:
        print("Fetching Travis County census tracts (NLCD skipped)...")

    if not settings.census_api_key:
        print("  Note: add CENSUS_API_KEY to .env for tract-level ACS population")

    geo_path = settings.data_dir / "processed" / "tracts.geojson"
    geojson = fetch_tract_geojson(geo_path)
    print(f"  → {len(geojson['features'])} tracts saved to {geo_path}")

    morph = load_morphology_table(rebuild=True)
    print(f"  → {len(morph)} tract morphology rows")
    print("Done.")


if __name__ == "__main__":
    main()
