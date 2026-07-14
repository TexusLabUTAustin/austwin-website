"""Hazard score helpers — prefer live USGS / ERCOT / precip observations."""

from __future__ import annotations

import numpy as np


def _clip01(x: float) -> float:
    return float(np.clip(x, 0.0, 1.0))


def flood_risk_from_obs(
    precip_in: float,
    gauge_stress: float,
    *,
    impervious: float = 0.4,
    drainage: float = 0.4,
) -> float:
    """
    0–100 flood risk from real precip + USGS gauge stress.
    Impervious/drainage (NLCD) only mildly amplify runoff potential.
    """
    precip_factor = _clip01(float(precip_in) / 0.5)  # ~0.5" / window → high
    gauge = _clip01(float(gauge_stress))
    runoff = _clip01(0.6 * float(impervious) + 0.4 * (1.0 - float(drainage)))
    # Observations dominate; land cover is a ±15% modulator
    base = 0.50 * gauge + 0.40 * precip_factor + 0.10 * runoff
    raw = 100.0 * base * (0.85 + 0.15 * runoff)
    return float(np.clip(raw, 0.0, 100.0))


def grid_stress_from_obs(
    heat_index_f: float,
    load_factor: float | None,
    pop_density: float,
    *,
    demand_mw: float | None = None,
    capacity_mw: float | None = None,
) -> float:
    """
    0–100 grid stress from live ERCOT utilization + heat + local density.
    Requires real load_factor; returns None-equivalent low score only if missing.
    """
    if load_factor is None:
        return float("nan")
    util = _clip01(float(load_factor))
    # Heat stress on cooling demand
    heat_factor = _clip01((float(heat_index_f) - 78.0) / 32.0)
    pop = float(pop_density)
    pop_factor = _clip01(pop if pop <= 1.5 else pop / 5000.0)
    # Utilization is the primary real signal
    raw = 100.0 * (0.55 * util + 0.30 * heat_factor + 0.15 * pop_factor)
    # Extra bump when reserves are thin (<15%)
    if capacity_mw and demand_mw and capacity_mw > 0:
        reserve = (capacity_mw - demand_mw) / capacity_mw
        if reserve < 0.15:
            raw = min(100.0, raw + 8.0 * (0.15 - reserve) / 0.15)
    return float(np.clip(raw, 0.0, 100.0))


# ---- training-time labels (same formulas; called with observed windows) ----

def flood_risk_score(
    precip_in: float,
    impervious: float,
    drainage: float,
    canopy: float = 0.25,
    gauge_stress: float = 0.0,
) -> float:
    return flood_risk_from_obs(
        precip_in,
        gauge_stress,
        impervious=impervious,
        drainage=drainage,
    )


def grid_stress_score(
    heat_index_f: float,
    pop_density: float,
    load_factor: float | None = None,
    hour_utc: int | None = None,
) -> float:
    if load_factor is None:
        # Training without ERCOT series: mild TOD prior only as label scaffold
        from datetime import datetime, timezone
        from math import sin, pi

        h = hour_utc if hour_utc is not None else datetime.now(timezone.utc).hour
        load_factor = float(0.55 + 0.45 * (0.5 + 0.5 * sin((h - 5) / 24.0 * 2 * pi)))
    return grid_stress_from_obs(heat_index_f, load_factor, pop_density)


def confidence_from_delta(
    delta: float,
    horizon: int,
    scale: float = 6.0,
    anomaly_severity: str | None = None,
) -> float:
    agree = 1.0 - min(1.0, abs(float(delta)) / scale)
    horizon_pen = 0.04 * max(0, int(horizon) - 1)
    conf = agree - horizon_pen
    if anomaly_severity in ("alert", "extreme"):
        conf -= 0.12 if anomaly_severity == "alert" else 0.20
    return float(np.clip(conf, 0.35, 0.95))


def score_confidence(score: float, horizon: int, base: float = 0.82) -> float:
    mid = 1.0 - abs(float(score) - 50.0) / 50.0
    conf = base - 0.10 * mid - 0.03 * max(0, int(horizon) - 1)
    return float(np.clip(conf, 0.4, 0.95))
