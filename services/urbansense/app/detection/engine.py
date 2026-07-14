"""Composite anomaly scoring per census tract."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from app.data.asos import latest_observed_heat_index, rolling_heat_index_std
from app.data.tracts import morphology_expected_heat_index
from app.detection.baselines import city_forecast_stats, station_level_forecast_proxy

WEIGHT_SPATIAL = 0.55
WEIGHT_TEMPORAL = 0.30
WEIGHT_MORPHOLOGY = 0.15

SEVERITY_THRESHOLDS = {
    "watch": 0.28,
    "alert": 0.42,
    "extreme": 0.62,
}


def _normalize_abs_z(value: float, scale: float) -> float:
    return float(np.clip(abs(value) / scale, 0.0, 1.0))


def score_to_severity(score: float) -> str:
    if score >= SEVERITY_THRESHOLDS["extreme"]:
        return "extreme"
    if score >= SEVERITY_THRESHOLDS["alert"]:
        return "alert"
    if score >= SEVERITY_THRESHOLDS["watch"]:
        return "watch"
    return "normal"


def compute_tract_anomalies(
    forecast_payload: dict,
    morphology: pd.DataFrame,
    *,
    horizon: int = 1,
) -> list[dict[str, Any]]:
    """Score each tract; return list of anomaly property dicts keyed by geoid."""
    features = forecast_payload.get("features", {}).get("features", [])
    if not features:
        return []

    city_median, city_std = city_forecast_stats(features, horizon)
    station_forecast = station_level_forecast_proxy(features, horizon)
    observed_hi = latest_observed_heat_index()
    temporal_std = rolling_heat_index_std()
    temporal_error = observed_hi - station_forecast
    temporal_score = _normalize_abs_z(temporal_error, temporal_std * 1.5)

    morph_by_geoid = morphology.set_index("geoid")
    base_hi = observed_hi

    results: list[dict[str, Any]] = []
    for feat in features:
        props = feat.get("properties", {})
        geoid = props.get("GEOID", "")
        tract_forecast = float(props.get("forecasts", {}).get(str(horizon), city_median))

        spatial_delta = tract_forecast - city_median
        spatial_score = _normalize_abs_z(spatial_delta, city_std * 2.0)

        morph_score = 0.0
        if geoid in morph_by_geoid.index:
            morph_row = morph_by_geoid.loc[geoid]
            expected = morphology_expected_heat_index(morph_row, base_hi)
            morph_score = _normalize_abs_z(tract_forecast - expected, city_std * 1.5)

        composite = (
            WEIGHT_SPATIAL * spatial_score
            + WEIGHT_TEMPORAL * temporal_score
            + WEIGHT_MORPHOLOGY * morph_score
        )
        composite = float(np.clip(composite, 0.0, 1.0))

        results.append(
            {
                "geoid": geoid,
                "anomaly_score": round(composite, 4),
                "severity": score_to_severity(composite),
                "horizon": horizon,
                "tract_forecast": round(tract_forecast, 2),
                "city_median": round(city_median, 2),
                "observed_heat_index": round(observed_hi, 2),
                "factors": {
                    "spatial": round(spatial_score, 4),
                    "temporal": round(temporal_score, 4),
                    "morphology": round(morph_score, 4),
                },
            }
        )

    return results
