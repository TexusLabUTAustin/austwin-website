"""ERCOT live system demand from the public supply-demand dashboard JSON."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import requests

from app.config import settings

CACHE_NAME = "ercot_load.json"
SUPPLY_DEMAND_URL = "https://www.ercot.com/api/1/services/read/dashboards/supply-demand.json"


def _cache_path() -> Path:
    return settings.data_dir / "processed" / CACHE_NAME


def fetch_load_factor(force: bool = False) -> dict:
    """
    Return live ERCOT demand / capacity.
    Fields: load_factor (0–1), demand_mw, capacity_mw, reserve_mw, source, timestamp.
    """
    path = _cache_path()
    if not force and path.exists():
        try:
            cached = json.loads(path.read_text())
            age = datetime.now(timezone.utc).timestamp() - cached.get("fetched_unix", 0)
            if age < 300 and cached.get("source", "").startswith("ercot"):
                return cached
        except Exception:
            pass

    if not settings.ercot_enabled:
        return _empty("ercot_disabled")

    try:
        resp = requests.get(
            SUPPLY_DEMAND_URL,
            timeout=20,
            headers={
                "User-Agent": "Mozilla/5.0 AusTwin-CityForesight/0.1",
                "Accept": "application/json",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        parsed = _parse_supply_demand(data)
        if parsed is None:
            return _cached_or_empty(path, "ercot_parse_failed")
        payload = {
            "fetched_unix": datetime.now(timezone.utc).timestamp(),
            **parsed,
            "source": "ercot_supply_demand",
            "last_updated": data.get("lastUpdated"),
        }
        path.write_text(json.dumps(payload))
        return payload
    except Exception:
        return _cached_or_empty(path, "ercot_fetch_failed")


def _parse_supply_demand(data: dict) -> dict | None:
    rows = data.get("data")
    if not isinstance(rows, list) or not rows:
        return None
    # Prefer the most recent row with non-zero demand
    latest = None
    for row in reversed(rows):
        if isinstance(row, dict) and row.get("demand"):
            latest = row
            break
    if latest is None:
        latest = rows[-1] if isinstance(rows[-1], dict) else None
    if not latest:
        return None
    try:
        demand = float(latest["demand"])
        capacity = float(latest.get("capacity") or 0.0)
    except (TypeError, ValueError, KeyError):
        return None
    if demand <= 0:
        return None
    if capacity <= 0:
        capacity = 85000.0
    load_factor = min(1.0, max(0.05, demand / capacity))
    return {
        "load_factor": round(load_factor, 4),
        "demand_mw": round(demand, 1),
        "capacity_mw": round(capacity, 1),
        "reserve_mw": round(capacity - demand, 1),
        "utilization_pct": round(100.0 * load_factor, 2),
        "timestamp": latest.get("timestamp"),
    }


def _cached_or_empty(path: Path, reason: str) -> dict:
    if path.exists():
        try:
            cached = json.loads(path.read_text())
            if cached.get("demand_mw"):
                cached["source"] = f"{cached.get('source', 'ercot')}_stale:{reason}"
                return cached
        except Exception:
            pass
    return _empty(reason)


def _empty(reason: str) -> dict:
    return {
        "fetched_unix": datetime.now(timezone.utc).timestamp(),
        "load_factor": None,
        "demand_mw": None,
        "capacity_mw": None,
        "reserve_mw": None,
        "utilization_pct": None,
        "source": reason,
        "timestamp": None,
    }
