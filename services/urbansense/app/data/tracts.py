"""Load tract boundaries and morphology from shared data/."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from app.config import settings


def load_tract_geojson(path: Path | None = None) -> dict:
    path = path or settings.data_dir / "processed" / "tracts.geojson"
    return json.loads(path.read_text())


def load_morphology_table(path: Path | None = None) -> pd.DataFrame:
    path = path or settings.data_dir / "processed" / "tract_morphology.csv"
    return pd.read_csv(path)


def morphology_expected_heat_index(morph: pd.Series, base_hi: float) -> float:
    """Morphology-grounded heat index expectation (mirrors CityForesight KIL)."""
    imp = morph["impervious_ratio"]
    canopy = morph["canopy_cover"]
    drain = morph["drainage_capacity"]
    mean_imp, mean_canopy = 0.52, 0.28
    delta = (
        6.5 * (imp - mean_imp)
        - 4.0 * (canopy - mean_canopy)
        - 1.5 * (drain - 0.55)
    )
    return float(base_hi + delta)
