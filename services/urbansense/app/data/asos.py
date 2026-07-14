"""ASOS weather utilities (shared data path with CityForesight)."""

from __future__ import annotations

import io
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from app.config import settings

MESONET_URL = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"


def heat_index_f(temp_f: np.ndarray, dewpoint_f: np.ndarray) -> np.ndarray:
    t = np.asarray(temp_f, dtype=np.float64)
    dp = np.asarray(dewpoint_f, dtype=np.float64)
    hi = 0.5 * (t + 61.0 + ((t - 68.0) * 1.2) + (dp * 0.094))
    mask = t >= 80.0
    if not np.any(mask):
        return hi
    tf = t[mask]
    rhf = np.clip(100.0 - 5.0 * (tf - dp[mask]), 0, 100)
    hi[mask] = (
        -42.379
        + 2.04901523 * tf
        + 10.14333127 * rhf
        - 0.22475541 * tf * rhf
        - 0.00683783 * tf**2
        - 0.05481717 * rhf**2
        + 0.00122874 * tf**2 * rhf
        + 0.00085282 * tf * rhf**2
        - 0.00000199 * tf**2 * rhf**2
    )
    return hi


def load_asos(path: Path | None = None) -> pd.DataFrame:
    path = path or settings.data_dir / "processed" / "asos_hourly.csv"
    return pd.read_csv(path, parse_dates=["valid"])


def fetch_latest_obs(station: str | None = None, hours: int = 48) -> pd.DataFrame:
    station = station or settings.station_id
    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=hours + 6)
    params = {
        "station": station,
        "data": "all",
        "year1": start.year,
        "month1": start.month,
        "day1": start.day,
        "year2": now.year,
        "month2": now.month,
        "day2": now.day,
        "tz": "Etc/UTC",
        "format": "onlycomma",
        "latlon": "no",
        "elev": "no",
        "missing": "M",
        "trace": "T",
        "direct": "no",
        "report_type": ["3", "4"],
    }
    resp = requests.get(MESONET_URL, params=params, timeout=60)
    resp.raise_for_status()
    df = pd.read_csv(io.StringIO(resp.text), na_values=["M"])
    df["valid"] = pd.to_datetime(df["valid"], utc=True)
    for col in ("tmpf", "dwpf", "sknt", "drct", "alti"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df["heat_index"] = heat_index_f(
        df["tmpf"].ffill().values,
        df["dwpf"].ffill().values,
    )
    hourly = (
        df.set_index("valid")
        .resample("1h")
        .agg(
            {
                "tmpf": "mean",
                "dwpf": "mean",
                "sknt": "mean",
                "drct": "mean",
                "alti": "mean",
                "heat_index": "mean",
            }
        )
        .dropna(subset=["tmpf", "dwpf"])
        .reset_index()
    )
    return hourly.tail(hours)


def latest_observed_heat_index(station: str | None = None) -> float:
    try:
        recent = fetch_latest_obs(station=station, hours=4)
        if len(recent):
            return float(recent["heat_index"].iloc[-1])
    except Exception:
        pass
    historical = load_asos()
    return float(historical["heat_index"].iloc[-1])


def rolling_heat_index_std(window_hours: int = 168) -> float:
    df = load_asos()
    tail = df["heat_index"].tail(window_hours)
    std = float(tail.std())
    return std if std > 0.5 else 3.0
