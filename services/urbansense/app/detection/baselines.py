"""Baseline statistics for anomaly detection."""

from __future__ import annotations

import statistics
from typing import Any


def city_forecast_stats(
    forecast_features: list[dict[str, Any]], horizon: int
) -> tuple[float, float]:
    """Return (median, std) of tract forecasts at a horizon."""
    values = []
    for feat in forecast_features:
        forecasts = feat.get("properties", {}).get("forecasts", {})
        v = forecasts.get(str(horizon))
        if v is not None:
            values.append(float(v))
    if not values:
        return 85.0, 5.0
    median = float(statistics.median(values))
    std = float(statistics.pstdev(values)) if len(values) > 1 else 3.0
    return median, max(std, 1.0)


def station_level_forecast_proxy(
    forecast_features: list[dict[str, Any]], horizon: int
) -> float:
    """City median as station-equivalent forecast for temporal comparison."""
    median, _ = city_forecast_stats(forecast_features, horizon)
    return median
