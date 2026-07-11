"""HTTP client for CityForesight forecast API."""

from __future__ import annotations

import httpx

from app.config import settings


def fetch_current_forecast() -> dict:
    url = f"{settings.cityforesight_url.rstrip('/')}/forecasts/current"
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.json()


def check_cityforesight_health() -> bool:
    url = f"{settings.cityforesight_url.rstrip('/')}/health"
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(url)
            return resp.status_code == 200
    except Exception:
        return False
