"""Live grounding: pull compact snapshots from CityForesight + UrbanSense APIs."""

from __future__ import annotations

import httpx

from app.config import settings


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


def forecast_snapshot(horizon: int = 1) -> str | None:
    """Compact text summary of the current tract heat-index forecast."""
    try:
        data = _get(f"{settings.cityforesight_url.rstrip('/')}/forecasts/current")
    except Exception:  # noqa: BLE001
        return None
    feats = data.get("features", {}).get("features", [])
    rows: list[tuple[str, float]] = []
    for f in feats:
        p = f.get("properties", {})
        val = (p.get("forecasts") or {}).get(str(horizon))
        if val is None:
            continue
        rows.append((p.get("NAME") or p.get("GEOID") or "?", float(val)))
    if not rows:
        return None
    rows.sort(key=lambda x: x[1], reverse=True)
    avg = sum(v for _, v in rows) / len(rows)
    hottest = "; ".join(f"{n} {v:.1f}F" for n, v in rows[:5])
    coolest = "; ".join(f"{n} {v:.1f}F" for n, v in rows[-3:])
    return (
        f"Live CityForesight forecast (+{horizon}h), updated {data.get('last_updated')}, "
        f"model {data.get('model')}:\n"
        f"- City-average heat index: {avg:.1f}F across {len(rows)} census tracts.\n"
        f"- Hottest tracts: {hottest}.\n"
        f"- Coolest tracts: {coolest}."
    )


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
