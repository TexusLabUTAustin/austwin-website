"""External Austin climate feeds — all free, no API key.

Open-Meteo: full meteorology + air quality for any point.
NWS (api.weather.gov): official forecast + active alerts.
Called server-side, so no browser CORS limits. Each returns compact text.
"""

from __future__ import annotations

import httpx

from app.config import settings

OPEN_METEO = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_AQ = "https://air-quality-api.open-meteo.com/v1/air-quality"
NWS_POINTS = "https://api.weather.gov/points"
NWS_ALERTS = "https://api.weather.gov/alerts/active"

_WMO = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "rime fog", 51: "light drizzle", 53: "drizzle", 55: "dense drizzle",
    61: "light rain", 63: "rain", 65: "heavy rain", 66: "freezing rain", 67: "freezing rain",
    71: "light snow", 73: "snow", 75: "heavy snow", 77: "snow grains",
    80: "light showers", 81: "showers", 82: "violent showers",
    85: "snow showers", 86: "snow showers",
    95: "thunderstorm", 96: "thunderstorm w/ hail", 99: "severe thunderstorm w/ hail",
}


def _weather_text(code) -> str:
    try:
        return _WMO.get(int(code), f"code {code}")
    except (TypeError, ValueError):
        return "unknown"


def _get(url: str, params: dict | None = None, headers: dict | None = None) -> dict:
    with httpx.Client(timeout=20.0) as client:
        resp = client.get(url, params=params, headers=headers)
        resp.raise_for_status()
        return resp.json()


def _nws_headers() -> dict:
    return {"User-Agent": settings.nws_user_agent, "Accept": "application/geo+json"}


def _aq_category(aqi) -> str:
    try:
        v = float(aqi)
    except (TypeError, ValueError):
        return ""
    for hi, label in (
        (50, "Good"), (100, "Moderate"), (150, "Unhealthy for sensitive groups"),
        (200, "Unhealthy"), (300, "Very unhealthy"),
    ):
        if v <= hi:
            return label
    return "Hazardous"


def current_conditions() -> str:
    try:
        d = _get(
            OPEN_METEO,
            {
                "latitude": settings.austin_lat,
                "longitude": settings.austin_lon,
                "current": (
                    "temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,"
                    "weather_code,cloud_cover,wind_speed_10m,wind_gusts_10m,surface_pressure,uv_index"
                ),
                "temperature_unit": "fahrenheit",
                "wind_speed_unit": "mph",
                "timezone": "America/Chicago",
            },
        )
    except Exception:  # noqa: BLE001
        return "Current weather feed unavailable."
    c = d.get("current", {})
    return (
        f"Current Austin conditions ({c.get('time')} CT): {_weather_text(c.get('weather_code'))}, "
        f"temp {c.get('temperature_2m')}F (feels {c.get('apparent_temperature')}F), "
        f"humidity {c.get('relative_humidity_2m')}%, wind {c.get('wind_speed_10m')} mph "
        f"(gusts {c.get('wind_gusts_10m')}), cloud {c.get('cloud_cover')}%, "
        f"precip {c.get('precipitation')} in, UV {c.get('uv_index')}, "
        f"pressure {c.get('surface_pressure')} hPa."
    )


def hourly_weather(hours: int = 12) -> str:
    hours = max(1, min(int(hours or 12), 48))
    try:
        d = _get(
            OPEN_METEO,
            {
                "latitude": settings.austin_lat,
                "longitude": settings.austin_lon,
                "hourly": (
                    "temperature_2m,apparent_temperature,precipitation_probability,"
                    "relative_humidity_2m,wind_speed_10m"
                ),
                "temperature_unit": "fahrenheit",
                "wind_speed_unit": "mph",
                "timezone": "America/Chicago",
                "forecast_days": 3,
            },
        )
    except Exception:  # noqa: BLE001
        return "Hourly forecast feed unavailable."
    h = d.get("hourly", {})
    times = h.get("time", [])
    now = d.get("current", {}).get("time")
    start = 0
    if now:
        for i, t in enumerate(times):
            if t >= now:
                start = i
                break
    end = start + hours
    temps = h.get("temperature_2m", [])[start:end]
    feels = h.get("apparent_temperature", [])[start:end]
    pop = h.get("precipitation_probability", [])[start:end]
    if not temps:
        return "No hourly data."
    return (
        f"Next {len(temps)}h Austin outlook: temp {min(temps):.0f}-{max(temps):.0f}F, "
        f"feels-like up to {max(feels):.0f}F, max precip chance {max(pop or [0])}%. "
        f"Hour-by-hour temps: {', '.join(f'{t:.0f}' for t in temps)}."
    )


def daily_outlook(days: int = 7) -> str:
    days = max(1, min(int(days or 7), 16))
    try:
        d = _get(
            OPEN_METEO,
            {
                "latitude": settings.austin_lat,
                "longitude": settings.austin_lon,
                "daily": (
                    "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,"
                    "precipitation_probability_max,uv_index_max,sunrise,sunset"
                ),
                "temperature_unit": "fahrenheit",
                "timezone": "America/Chicago",
                "forecast_days": days,
            },
        )
    except Exception:  # noqa: BLE001
        return "Daily outlook feed unavailable."
    dd = d.get("daily", {})
    times = dd.get("time", [])
    lines = []
    for i, day in enumerate(times[:days]):
        lines.append(
            f"{day}: {_weather_text(dd['weather_code'][i])}, "
            f"{dd['temperature_2m_min'][i]:.0f}-{dd['temperature_2m_max'][i]:.0f}F, "
            f"precip {dd['precipitation_sum'][i]} in "
            f"({dd['precipitation_probability_max'][i]}% chance), UV max {dd['uv_index_max'][i]}"
        )
    return "Austin daily outlook:\n" + "\n".join(lines)


def air_quality() -> str:
    try:
        d = _get(
            OPEN_METEO_AQ,
            {
                "latitude": settings.austin_lat,
                "longitude": settings.austin_lon,
                "current": "pm2_5,pm10,ozone,nitrogen_dioxide,us_aqi",
                "timezone": "America/Chicago",
            },
        )
    except Exception:  # noqa: BLE001
        return "Air-quality feed unavailable."
    c = d.get("current", {})
    aqi = c.get("us_aqi")
    return (
        f"Austin air quality ({c.get('time')} CT): US AQI {aqi} ({_aq_category(aqi)}). "
        f"PM2.5 {c.get('pm2_5')} µg/m³, PM10 {c.get('pm10')}, ozone {c.get('ozone')}, "
        f"NO2 {c.get('nitrogen_dioxide')}."
    )


def weather_alerts() -> str:
    try:
        d = _get(
            NWS_ALERTS,
            {"point": f"{settings.austin_lat},{settings.austin_lon}"},
            _nws_headers(),
        )
    except Exception:  # noqa: BLE001
        return "NWS alert feed unavailable."
    feats = d.get("features", [])
    if not feats:
        return "No active NWS weather alerts for the Austin area right now."
    out = []
    for f in feats[:6]:
        p = f.get("properties", {})
        out.append(f"{p.get('event')} — {p.get('severity')}/{p.get('urgency')}: {p.get('headline')}")
    return "Active NWS alerts for Austin:\n" + "\n".join(out)


def official_forecast(periods: int = 4) -> str:
    periods = max(1, min(int(periods or 4), 8))
    try:
        point = _get(
            f"{NWS_POINTS}/{settings.austin_lat},{settings.austin_lon}", None, _nws_headers()
        )
        url = point["properties"]["forecast"]
        fc = _get(url, None, _nws_headers())
    except Exception:  # noqa: BLE001
        return "NWS official forecast unavailable."
    out = []
    for p in fc.get("properties", {}).get("periods", [])[:periods]:
        out.append(f"{p.get('name')}: {p.get('detailedForecast')}")
    return "NWS official Austin forecast:\n" + "\n".join(out)
