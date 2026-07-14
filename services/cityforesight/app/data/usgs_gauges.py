"""Live USGS stream gauges for Austin / Travis County flood context."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import requests

from app.config import settings

CACHE_NAME = "usgs_austin_gauges.json"

# Austin-area USGS sites (creeks + Colorado). Guadalupe at Comfort is too far — omit.
AUSTIN_SITES = [
    "08155240",  # Barton Ck Lost Creek
    "08155300",  # Barton Ck Loop 360
    "08158000",  # Colorado Rv at Austin
    "08158200",  # Walnut Ck Dessau
    "08158700",  # Onion Ck Driftwood
    "08158930",  # Williamson Ck Manchaca
    "08155500",  # Onion Ck at US 183 (if active)
    "08158840",  # Onion Ck Twin Creeks
]

# Approximate flood / action stages (ft) from NWS / USGS where known; else None → relative.
FLOOD_STAGE_FT = {
    "08158000": 20.5,   # Colorado at Austin (action ~16–20 depending on source)
    "08158930": 8.0,    # Williamson Manchaca
    "08158200": 12.0,   # Walnut Dessau
    "08155300": 8.0,    # Barton Loop 360
    "08155240": 10.0,   # Barton Lost Creek
    "08158700": 13.0,   # Onion Driftwood
}


def _cache_path() -> Path:
    return settings.data_dir / "processed" / CACHE_NAME


def fetch_gauge_snapshot(force: bool = False) -> dict:
    """
    Latest gage height + discharge for Austin USGS sites.
    Returns {gauges: [...], city_flood_factor: 0–1, source, fetched_unix}.
    """
    path = _cache_path()
    if not force and path.exists():
        try:
            cached = json.loads(path.read_text())
            age = datetime.now(timezone.utc).timestamp() - cached.get("fetched_unix", 0)
            if age < 600:
                return cached
        except Exception:
            pass

    sites = ",".join(AUSTIN_SITES)
    url = (
        "https://waterservices.usgs.gov/nwis/iv/"
        f"?format=json&sites={sites}&parameterCd=00060,00065&siteStatus=all"
    )
    try:
        resp = requests.get(url, timeout=25, headers={"User-Agent": "AusTwin-CityForesight/0.1"})
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        if path.exists():
            cached = json.loads(path.read_text())
            cached["source"] = "usgs_stale"
            return cached
        return {
            "fetched_unix": datetime.now(timezone.utc).timestamp(),
            "gauges": [],
            "city_flood_factor": 0.0,
            "source": "usgs_unavailable",
        }

    by_site: dict[str, dict] = {}
    for series in data.get("value", {}).get("timeSeries", []):
        info = series.get("sourceInfo", {})
        site = info.get("siteCode", [{}])[0].get("value")
        if not site:
            continue
        geo = info.get("geoLocation", {}).get("geogLocation", {})
        lat = geo.get("latitude")
        lon = geo.get("longitude")
        name = info.get("siteName", site)
        var = series.get("variable", {}).get("variableCode", [{}])[0].get("value")
        vals = series.get("values", [{}])[0].get("value", [])
        if not vals:
            continue
        latest = vals[-1]
        try:
            value = float(latest.get("value"))
        except (TypeError, ValueError):
            continue
        entry = by_site.setdefault(
            site,
            {
                "site": site,
                "name": name,
                "lat": float(lat) if lat is not None else None,
                "lon": float(lon) if lon is not None else None,
                "discharge_cfs": None,
                "gage_height_ft": None,
                "observed": latest.get("dateTime"),
            },
        )
        if var == "00060":
            entry["discharge_cfs"] = value
        elif var == "00065":
            entry["gage_height_ft"] = value

    gauges = []
    stresses = []
    for site, g in by_site.items():
        stress = _gauge_stress(g)
        g["stress"] = round(stress, 3)
        g["flood_stage_ft"] = FLOOD_STAGE_FT.get(site)
        gauges.append(g)
        if g.get("lat") is not None:
            stresses.append(stress)

    city = max(stresses) if stresses else 0.0
    # Soften Colorado mainstem dominance: also take median of creek stresses
    creek = [g["stress"] for g in gauges if g["site"] != "08158000"]
    if creek:
        city = 0.55 * city + 0.45 * (sum(creek) / len(creek))

    payload = {
        "fetched_unix": datetime.now(timezone.utc).timestamp(),
        "gauges": gauges,
        "city_flood_factor": round(min(1.0, city), 3),
        "source": "usgs_nwis_iv",
        "gauge_count": len(gauges),
    }
    path.write_text(json.dumps(payload))
    return payload


def _gauge_stress(g: dict) -> float:
    """0–1 stress from gage height vs flood stage, else discharge heuristic."""
    gh = g.get("gage_height_ft")
    stage = FLOOD_STAGE_FT.get(g["site"])
    if gh is not None and stage:
        # 0 at ~40% of flood stage, 1 at flood stage+
        return float(min(1.0, max(0.0, (gh - 0.4 * stage) / (0.6 * stage))))
    q = g.get("discharge_cfs")
    if q is None:
        return 0.0
    # log scale; 500 cfs on a creek is elevated, 5000+ severe
    return float(min(1.0, math.log1p(max(0.0, q)) / math.log1p(2500.0)))


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def local_gauge_stress(lat: float, lon: float, snapshot: dict, max_km: float = 18.0) -> float:
    """Inverse-distance weighted gauge stress at a tract centroid."""
    gauges = snapshot.get("gauges") or []
    num = 0.0
    den = 0.0
    for g in gauges:
        if g.get("lat") is None or g.get("lon") is None:
            continue
        d = haversine_km(lat, lon, g["lat"], g["lon"])
        if d > max_km:
            continue
        w = 1.0 / max(d, 0.5) ** 2
        num += w * float(g.get("stress") or 0.0)
        den += w
    if den <= 0:
        return float(snapshot.get("city_flood_factor") or 0.0)
    return float(min(1.0, num / den))
