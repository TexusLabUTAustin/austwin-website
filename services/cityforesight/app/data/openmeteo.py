"""Open-Meteo helpers — precip + temperature for Austin (no API key)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import requests

from app.config import settings

AUSTIN_LAT = 30.27
AUSTIN_LON = -97.74
CACHE_NAME = "openmeteo_austin.json"


def _cache_path() -> Path:
    return settings.data_dir / "processed" / CACHE_NAME


def fetch_austin_weather(hours: int = 48, force: bool = False) -> dict:
    """
    Hourly precipitation (mm) and temperature (°C) near downtown Austin.
    Cached under data/processed/ for offline / rate-limit resilience.
    """
    path = _cache_path()
    if not force and path.exists():
        try:
            cached = json.loads(path.read_text())
            age = datetime.now(timezone.utc).timestamp() - cached.get("fetched_unix", 0)
            if age < 1800:  # 30 min
                return cached
        except Exception:
            pass

    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": AUSTIN_LAT,
        "longitude": AUSTIN_LON,
        "hourly": "temperature_2m,precipitation,soil_temperature_0cm",
        "forecast_days": 2,
        "past_days": 1,
        "timezone": "UTC",
    }
    try:
        resp = requests.get(url, params=params, timeout=20)
        resp.raise_for_status()
        hourly = resp.json().get("hourly", {})
        payload = {
            "fetched_unix": datetime.now(timezone.utc).timestamp(),
            "latitude": AUSTIN_LAT,
            "longitude": AUSTIN_LON,
            "time": hourly.get("time", []),
            "temperature_2m": hourly.get("temperature_2m", []),
            "precipitation_mm": hourly.get("precipitation", []),
            "soil_temperature_0cm": hourly.get("soil_temperature_0cm", []),
            "source": "open-meteo",
        }
        path.write_text(json.dumps(payload))
        return payload
    except Exception:
        if path.exists():
            return json.loads(path.read_text())
        return {
            "fetched_unix": 0,
            "time": [],
            "temperature_2m": [],
            "precipitation_mm": [],
            "soil_temperature_0cm": [],
            "source": "empty",
        }


def recent_precip_inches(hours: int = 3) -> float:
    """Sum of recent precip (inches) from Open-Meteo cache/live."""
    data = fetch_austin_weather()
    precip = data.get("precipitation_mm") or []
    if not precip:
        return 0.0
    window = precip[-hours:] if len(precip) >= hours else precip
    mm = sum(float(x or 0.0) for x in window)
    return mm / 25.4


def current_temp_c() -> float | None:
    data = fetch_austin_weather()
    temps = data.get("temperature_2m") or []
    if not temps:
        return None
    for t in reversed(temps):
        if t is not None:
            return float(t)
    return None
