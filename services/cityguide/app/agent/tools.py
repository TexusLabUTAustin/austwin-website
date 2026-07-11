"""Agent tools — every CityForesight / UrbanSense capability + KB search + analytics.

Each tool takes plain kwargs (lenient) and returns a compact text observation the
LLM can reason over. Tools fetch live data on demand, so the agent can chain them
to answer complex, multi-step questions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.clients import climate, systemdata
from app.rag import store

SEVERITY_RANK = {"normal": 0, "watch": 1, "alert": 2, "extreme": 3}


def _features(payload: dict) -> list[dict]:
    return payload.get("features", {}).get("features", [])


def _name(props: dict) -> str:
    return props.get("NAME") or props.get("GEOID") or "?"


def _resolve_geoid(needle: str) -> tuple[str | None, str | None]:
    """Map a tract name or GEOID (possibly partial) to (geoid, name)."""
    needle = str(needle).strip().lower()
    try:
        feats = _features(systemdata.fetch_forecast())
    except Exception:  # noqa: BLE001
        return None, None
    # exact geoid / name first, then substring
    for exact in (True, False):
        for f in feats:
            p = f.get("properties", {})
            geoid = str(p.get("GEOID", "")).lower()
            name = str(p.get("NAME", "")).lower()
            if exact:
                if needle == geoid or needle == name:
                    return p.get("GEOID"), p.get("NAME")
            elif needle and (needle in name or needle in geoid or geoid.endswith(needle)):
                return p.get("GEOID"), p.get("NAME")
    return None, None


# --- Tool implementations -------------------------------------------------

def rank_tracts(order: str = "hottest", horizon: Any = 1, limit: Any = 5, **_: Any) -> str:
    horizon = int(horizon or 1)
    limit = max(1, min(int(limit or 5), 20))
    rows = []
    for f in _features(systemdata.fetch_forecast()):
        p = f.get("properties", {})
        v = (p.get("forecasts") or {}).get(str(horizon))
        if v is not None:
            rows.append((_name(p), float(v)))
    if not rows:
        return "No forecast data available."
    rows.sort(key=lambda x: x[1], reverse=(order != "coolest"))
    picked = rows[:limit]
    label = "Coolest" if order == "coolest" else "Hottest"
    body = "; ".join(f"{n} {v:.1f}F" for n, v in picked)
    return f"{label} {len(picked)} tracts at +{horizon}h: {body}."


def city_summary(horizon: Any = 1, **_: Any) -> str:
    horizon = int(horizon or 1)
    payload = systemdata.fetch_forecast()
    vals = []
    for f in _features(payload):
        v = (f.get("properties", {}).get("forecasts") or {}).get(str(horizon))
        if v is not None:
            vals.append(float(v))
    if not vals:
        return "No forecast data available."
    vals.sort()
    n = len(vals)
    avg = sum(vals) / n
    median = vals[n // 2]
    danger = sum(1 for v in vals if v >= 103)
    caution = sum(1 for v in vals if 90 <= v < 103)
    return (
        f"City summary at +{horizon}h (updated {payload.get('last_updated')}, "
        f"model {payload.get('model')}): {n} tracts, average {avg:.1f}F, median {median:.1f}F, "
        f"range {vals[0]:.1f}-{vals[-1]:.1f}F. In caution band (90-103F): {caution}; "
        f"in danger band (>=103F): {danger}."
    )


def get_tract(tract: str = "", horizon: Any = 1, **_: Any) -> str:
    geoid, name = _resolve_geoid(tract)
    if not geoid:
        return f"No tract matched '{tract}'. Use a name like 'Census Tract 6.06' or a GEOID."
    try:
        d = systemdata.fetch_tract_forecast(geoid)
    except Exception:  # noqa: BLE001
        return f"Could not fetch forecast for {name}."
    fc = d.get("forecasts", {})
    series = "; ".join(f"+{h}h {float(v):.1f}F" for h, v in sorted(fc.items(), key=lambda kv: int(kv[0])))
    m = d.get("morphology") or {}

    def pct(x):
        return f"{float(x) * 100:.0f}%" if isinstance(x, (int, float)) else "n/a"

    morph = (
        f"impervious {pct(m.get('impervious_ratio'))}, canopy {pct(m.get('canopy_cover'))}, "
        f"drainage {pct(m.get('drainage_capacity'))}"
    )
    return f"{name} ({geoid}) forecast: {series}. Morphology: {morph}."


def list_anomalies(min_severity: str = "watch", limit: Any = 8, **_: Any) -> str:
    try:
        payload = systemdata.fetch_anomalies()
    except Exception:  # noqa: BLE001
        return "UrbanSense anomaly service is unavailable."
    limit = max(1, min(int(limit or 8), 20))
    floor = SEVERITY_RANK.get(str(min_severity).lower(), 1)
    rows = []
    for f in _features(payload):
        p = f.get("properties", {})
        sev = p.get("severity", "normal")
        score = p.get("anomaly_score")
        if score is None or SEVERITY_RANK.get(sev, 0) < floor:
            continue
        rows.append((_name(p), float(score), sev))
    rows.sort(key=lambda x: x[1], reverse=True)
    s = payload.get("summary", {})
    head = (
        f"Anomaly summary (+{payload.get('horizon')}h, updated {payload.get('last_updated')}): "
        f"watch {s.get('watch', 0)}, alert {s.get('alert', 0)}, extreme {s.get('extreme', 0)}."
    )
    if not rows:
        return head + f" No tracts at severity '{min_severity}' or above."
    body = "; ".join(f"{n} ({sev}, {sc:.2f})" for n, sc, sev in rows[:limit])
    return head + f" Top: {body}."


def get_tract_anomaly(tract: str = "", **_: Any) -> str:
    geoid, name = _resolve_geoid(tract)
    if not geoid:
        return f"No tract matched '{tract}'."
    try:
        d = systemdata.fetch_tract_anomaly(geoid)
    except Exception:  # noqa: BLE001
        return f"No anomaly detail available for {name}."
    a = d.get("anomaly", {})
    fac = a.get("factors", {})
    return (
        f"{name} ({geoid}) anomaly: score {a.get('anomaly_score')}, severity {a.get('severity')}, "
        f"tract forecast {a.get('tract_forecast')}F vs city median {a.get('city_median')}F, "
        f"observed {a.get('observed_heat_index')}F. Factors — spatial {fac.get('spatial')}, "
        f"temporal {fac.get('temporal')}, morphology {fac.get('morphology')}."
    )


def lookup_address(query: str = "", **_: Any) -> str:
    try:
        r = systemdata.search_address(query)
    except Exception:  # noqa: BLE001
        return f"Could not geocode '{query}' (address may be outside Travis County coverage)."
    if r.get("candidates") and not r.get("geoid"):
        cands = "; ".join(c.get("matched_address", "?") for c in r["candidates"][:4])
        return f"Multiple matches for '{query}': {cands}. Ask the user to pick one."
    fc = r.get("forecasts", {})
    series = "; ".join(f"+{h}h {float(v):.1f}F" for h, v in sorted(fc.items(), key=lambda kv: int(kv[0])))
    return (
        f"Address '{r.get('matched_address')}' is in {r.get('name')} ({r.get('geoid')}). "
        f"Forecast: {series}. {r.get('coverage_note', '')}"
    )


def model_benchmark(**_: Any) -> str:
    try:
        b = systemdata.fetch_benchmark()
    except Exception:  # noqa: BLE001
        return "Benchmark not available."
    return (
        f"Model benchmark: baseline RMSE {b.get('baseline_rmse')}, KIL RMSE {b.get('kil_rmse')}, "
        f"improvement {b.get('improvement_pct')}% (gate passed: {b.get('gate_passed')})."
    )


def search_knowledge(query: str = "", **_: Any) -> str:
    retrieved, max_cos = store.retrieve(query)
    hits = [r for r in retrieved if r.cosine >= 0.2]
    if not hits:
        return "No relevant knowledge-base entry found."
    return "\n\n".join(f"[{r.chunk.doc}: {r.chunk.title}]\n{r.chunk.text}" for r in hits[:3])


@dataclass
class Tool:
    name: str
    description: str
    fn: Callable[..., str]
    live_source: str | None = None


TOOLS: dict[str, Tool] = {
    "rank_tracts": Tool(
        "rank_tracts",
        "List hottest or coolest tracts. Args: order ('hottest'|'coolest'), horizon (1-6), limit.",
        rank_tracts, "CityForesight forecast",
    ),
    "city_summary": Tool(
        "city_summary",
        "City-wide heat stats at a horizon: average, median, range, caution/danger counts. Args: horizon.",
        city_summary, "CityForesight forecast",
    ),
    "get_tract": Tool(
        "get_tract",
        "Full forecast (all horizons) + land-cover morphology for one tract. Args: tract (name or GEOID), horizon.",
        get_tract, "CityForesight forecast",
    ),
    "list_anomalies": Tool(
        "list_anomalies",
        "Current heat anomalies. Args: min_severity ('watch'|'alert'|'extreme'), limit.",
        list_anomalies, "UrbanSense anomalies",
    ),
    "get_tract_anomaly": Tool(
        "get_tract_anomaly",
        "Anomaly score, severity, and contributing factors for one tract. Args: tract.",
        get_tract_anomaly, "UrbanSense anomalies",
    ),
    "lookup_address": Tool(
        "lookup_address",
        "Geocode a street address or place and return the tract forecast there. Args: query.",
        lookup_address, "CityForesight forecast",
    ),
    "model_benchmark": Tool(
        "model_benchmark",
        "Forecasting model accuracy vs the baseline (RMSE, improvement). No args.",
        model_benchmark, None,
    ),
    "search_knowledge": Tool(
        "search_knowledge",
        "Search the knowledge base for definitions, protocols, and how the system works. Args: query.",
        search_knowledge, None,
    ),
    # --- External Austin climate feeds (Open-Meteo + NWS, live) ---
    "current_weather": Tool(
        "current_weather",
        "Actual current Austin weather now: temp, feels-like, humidity, wind, precip, cloud, UV, pressure. No args.",
        lambda **_: climate.current_conditions(), "Open-Meteo (live)",
    ),
    "hourly_weather": Tool(
        "hourly_weather",
        "Hour-by-hour Austin weather outlook (temp, feels-like, precip chance). Args: hours (1-48).",
        lambda hours=12, **_: climate.hourly_weather(hours), "Open-Meteo (live)",
    ),
    "weather_outlook": Tool(
        "weather_outlook",
        "Multi-day Austin forecast: highs/lows, precip, UV, conditions. Args: days (1-16).",
        lambda days=7, **_: climate.daily_outlook(days), "Open-Meteo (live)",
    ),
    "air_quality": Tool(
        "air_quality",
        "Current Austin air quality: US AQI, PM2.5, PM10, ozone, NO2. No args.",
        lambda **_: climate.air_quality(), "Open-Meteo air quality (live)",
    ),
    "weather_alerts": Tool(
        "weather_alerts",
        "Active NWS weather alerts/advisories/warnings for the Austin area. No args.",
        lambda **_: climate.weather_alerts(), "NWS alerts (live)",
    ),
    "official_forecast": Tool(
        "official_forecast",
        "NWS official Austin forecast in plain language (today, tonight, coming days). Args: periods (1-8).",
        lambda periods=4, **_: climate.official_forecast(periods), "NWS forecast (live)",
    ),
}


def run_tool(name: str, args: dict) -> tuple[str, str | None]:
    tool = TOOLS.get(name)
    if not tool:
        return f"Unknown tool '{name}'.", None
    try:
        return tool.fn(**(args or {})), tool.live_source
    except Exception as exc:  # noqa: BLE001
        return f"Tool '{name}' failed: {type(exc).__name__}: {exc}", None


def tools_doc() -> str:
    return "\n".join(f"- {t.name}: {t.description}" for t in TOOLS.values())
