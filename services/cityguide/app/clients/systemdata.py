"""Live grounding: pull compact snapshots from CityForesight + UrbanSense APIs."""

from __future__ import annotations

import httpx

from app.config import settings

HAZARD_KEYS = {
    "heat": "forecasts",
    "flood": "flood_forecasts",
    "grid": "grid_forecasts",
}


def _get(url: str, params: dict | None = None) -> dict:
    with httpx.Client(timeout=20.0) as client:
        resp = client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


def _cf(path: str, params: dict | None = None) -> dict:
    return _get(f"{settings.cityforesight_url.rstrip('/')}{path}", params)


def _us(path: str, params: dict | None = None) -> dict:
    return _get(f"{settings.urbansense_url.rstrip('/')}{path}", params)


# --- Raw fetchers used by the agent tools --------------------------------

def fetch_forecast() -> dict:
    return _cf("/forecasts/current")


def fetch_anomalies() -> dict:
    return _us("/anomalies/current")


def fetch_tract_forecast(geoid: str) -> dict:
    return _cf(f"/forecasts/tract/{geoid}")


def fetch_tract_anomaly(geoid: str) -> dict:
    return _us(f"/anomalies/tract/{geoid}")


def search_address(query: str) -> dict:
    return _cf("/forecasts/search", {"q": query})


def fetch_benchmark() -> dict:
    return _cf("/metrics/benchmark")


def _health(url: str) -> bool:
    try:
        return _get(f"{url.rstrip('/')}/health").get("status") in ("ok", "degraded")
    except Exception:  # noqa: BLE001
        return False


def health() -> dict:
    return {
        "cityforesight": _health(settings.cityforesight_url),
        "urbansense": _health(settings.urbansense_url),
    }


def _hazard_rows(data: dict, hazard: str, horizon: int) -> list[tuple[str, float]]:
    key = HAZARD_KEYS.get(hazard, "forecasts")
    rows: list[tuple[str, float]] = []
    for f in data.get("features", {}).get("features", []):
        p = f.get("properties", {})
        val = (p.get(key) or {}).get(str(horizon))
        if val is None:
            continue
        rows.append((p.get("NAME") or p.get("GEOID") or "?", float(val)))
    return rows


def _fmt_unit(hazard: str, v: float) -> str:
    if hazard == "heat":
        return f"{v:.1f}F"
    return f"{v:.0f}/100"


def forecast_snapshot(horizon: int = 1, hazard: str = "heat") -> str | None:
    """Compact text summary of the current tract forecast for one hazard."""
    hazard = (hazard or "heat").lower()
    if hazard not in HAZARD_KEYS:
        hazard = "heat"
    try:
        data = _get(f"{settings.cityforesight_url.rstrip('/')}/forecasts/current")
    except Exception:  # noqa: BLE001
        return None
    rows = _hazard_rows(data, hazard, horizon)
    if not rows:
        return None
    rows.sort(key=lambda x: x[1], reverse=True)
    avg = sum(v for _, v in rows) / len(rows)
    top = "; ".join(f"{n} {_fmt_unit(hazard, v)}" for n, v in rows[:5])
    bottom = "; ".join(f"{n} {_fmt_unit(hazard, v)}" for n, v in rows[-3:])
    noun = {"heat": "heat index", "flood": "flood risk", "grid": "grid stress"}[hazard]
    return (
        f"Live CityForesight {noun} (+{horizon}h), updated {data.get('last_updated')}, "
        f"model {data.get('model')}:\n"
        f"- City-average {noun}: {_fmt_unit(hazard, avg)} across {len(rows)} census tracts.\n"
        f"- Highest tracts: {top}.\n"
        f"- Lowest tracts: {bottom}."
    )


def inputs_snapshot() -> str | None:
    """Live ERCOT / USGS / precip inputs that drive flood & grid scores."""
    try:
        data = _get(f"{settings.cityforesight_url.rstrip('/')}/forecasts/current")
    except Exception:  # noqa: BLE001
        return None
    inp = data.get("inputs") or {}
    if not inp:
        return None
    lines = [
        f"Live CityForesight hazard inputs (updated {data.get('last_updated')}):",
        f"- Precip: {inp.get('precip_in_6h', 'n/a')} in / 6h (source {inp.get('precip_source', '?')}).",
        (
            f"- ERCOT: demand {inp.get('ercot_demand_mw')} MW, capacity {inp.get('ercot_capacity_mw')} MW, "
            f"utilization {inp.get('ercot_utilization_pct')}% "
            f"(source {inp.get('ercot_source', '?')}, as of {inp.get('ercot_timestamp', '?')})."
        ),
        (
            f"- USGS: {inp.get('usgs_gauge_count', 0)} gauges, city stream-stress factor "
            f"{inp.get('usgs_city_flood_factor')} (source {inp.get('usgs_source', '?')})."
        ),
    ]
    gauges = inp.get("usgs_top_gauges") or []
    if gauges:
        gtxt = "; ".join(
            f"{g.get('name', g.get('site'))}: "
            f"{g.get('gage_height_ft')} ft"
            + (f", {g.get('discharge_cfs')} cfs" if g.get("discharge_cfs") is not None else "")
            + f" (stress {g.get('stress')})"
            for g in gauges[:4]
        )
        lines.append(f"- Top gauges: {gtxt}.")
    return "\n".join(lines)


def multi_hazard_snapshot(horizon: int = 1) -> str | None:
    """City averages for heat + flood + grid in one block."""
    try:
        data = _get(f"{settings.cityforesight_url.rstrip('/')}/forecasts/current")
    except Exception:  # noqa: BLE001
        return None
    parts = [f"Live multi-hazard snapshot (+{horizon}h, updated {data.get('last_updated')}):"]
    for hazard, noun in (
        ("heat", "heat index"),
        ("flood", "flood risk"),
        ("grid", "grid stress"),
    ):
        rows = _hazard_rows(data, hazard, horizon)
        if not rows:
            continue
        avg = sum(v for _, v in rows) / len(rows)
        hi = max(rows, key=lambda x: x[1])
        parts.append(
            f"- {noun}: avg {_fmt_unit(hazard, avg)}, highest {hi[0]} {_fmt_unit(hazard, hi[1])}."
        )
    inp = data.get("inputs") or {}
    if inp.get("ercot_utilization_pct") is not None or inp.get("usgs_gauge_count"):
        parts.append(
            f"- Feeds: precip {inp.get('precip_in_6h')} in/6h; "
            f"ERCOT util {inp.get('ercot_utilization_pct')}%; "
            f"USGS gauges {inp.get('usgs_gauge_count')}."
        )
    return "\n".join(parts) if len(parts) > 1 else None


def anomaly_snapshot() -> str | None:
    """Compact text summary of current UrbanSense heat anomalies."""
    try:
        data = _get(f"{settings.urbansense_url.rstrip('/')}/anomalies/current")
    except Exception:  # noqa: BLE001
        return None
    summary = data.get("summary", {})
    feats = data.get("features", {}).get("features", [])
    scored: list[tuple[str, float, str]] = []
    for f in feats:
        p = f.get("properties", {})
        score = p.get("anomaly_score")
        if score is None:
            continue
        scored.append(
            (p.get("NAME") or p.get("GEOID") or "?", float(score), p.get("severity") or "normal")
        )
    scored.sort(key=lambda x: x[1], reverse=True)
    top = "; ".join(f"{n} ({sev}, {sc:.2f})" for n, sc, sev in scored[:5]) or "none"
    return (
        f"Live UrbanSense anomalies (+{data.get('horizon')}h), updated {data.get('last_updated')}:\n"
        f"- Watch: {summary.get('watch', 0)}, Alert: {summary.get('alert', 0)}, "
        f"Extreme: {summary.get('extreme', 0)}, max score {summary.get('max_score', 0):.2f}.\n"
        f"- Most anomalous tracts: {top}."
    )
