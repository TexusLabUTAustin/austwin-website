"""Geocode addresses via OpenStreetMap Nominatim (server-side proxy)."""

from __future__ import annotations

from dataclasses import dataclass

import requests

from app.config import settings

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


@dataclass(frozen=True)
class GeocodeResult:
    lat: float
    lon: float
    display_name: str


def geocode_query(query: str) -> list[GeocodeResult]:
    """Return up to 5 geocode candidates for a free-text address or place name."""
    viewbox = (
        f"{settings.geocode_viewbox_west},"
        f"{settings.geocode_viewbox_north},"
        f"{settings.geocode_viewbox_east},"
        f"{settings.geocode_viewbox_south}"
    )
    params = {
        "q": query,
        "format": "json",
        "limit": 5,
        "countrycodes": "us",
        "viewbox": viewbox,
        "bounded": 0,
    }
    headers = {"User-Agent": settings.geocode_user_agent}
    try:
        resp = requests.get(NOMINATIM_URL, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError("Geocoding service unavailable") from exc

    results: list[GeocodeResult] = []
    for item in resp.json():
        try:
            results.append(
                GeocodeResult(
                    lat=float(item["lat"]),
                    lon=float(item["lon"]),
                    display_name=str(item.get("display_name", query)),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return results
