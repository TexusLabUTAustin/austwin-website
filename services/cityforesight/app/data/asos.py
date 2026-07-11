"""ASOS weather data utilities."""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from app.config import settings

MESONET_URL = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"


def heat_index_f(temp_f: np.ndarray, dewpoint_f: np.ndarray) -> np.ndarray:
    """NOAA heat index (°F) from temperature and dewpoint."""
    t = np.asarray(temp_f, dtype=np.float64)
    dp = np.asarray(dewpoint_f, dtype=np.float64)
    hi = 0.5 * (t + 61.0 + ((t - 68.0) * 1.2) + (dp * 0.094))
    mask = t >= 80.0
    if not np.any(mask):
        return hi
    tf = t[mask]
    rhf = np.clip(100.0 - 5.0 * (tf - dp[mask]), 0, 100)
    hi_mask = (
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
    hi[mask] = hi_mask
    return hi


def fetch_asos(
    station: str = "KAUS",
    year1: int = 2018,
    year2: int = 2024,
    output_path: Path | None = None,
) -> pd.DataFrame:
    """Download hourly ASOS observations from Iowa Environmental Mesonet."""
    params = {
        "station": station,
        "data": "all",
        "year1": year1,
        "month1": 1,
        "day1": 1,
        "year2": year2,
        "month2": 12,
        "day2": 31,
        "tz": "Etc/UTC",
        "format": "onlycomma",
        "latlon": "no",
        "elev": "no",
        "missing": "M",
        "trace": "T",
        "direct": "no",
        "report_type": ["3", "4"],
    }
    resp = requests.get(MESONET_URL, params=params, timeout=120)
    resp.raise_for_status()
    df = pd.read_csv(io.StringIO(resp.text), na_values=["M"])
    df["valid"] = pd.to_datetime(df["valid"], utc=True)
    df = df.sort_values("valid").reset_index(drop=True)

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

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        hourly.to_csv(output_path, index=False)

    return hourly


def load_asos(path: Path | None = None) -> pd.DataFrame:
    path = path or settings.data_dir / "processed" / "asos_hourly.csv"
    if not path.exists():
        return fetch_asos(output_path=path)
    return pd.read_csv(path, parse_dates=["valid"])


def fetch_latest_obs(station: str = "KAUS", hours: int = 48) -> pd.DataFrame:
    """Fetch recent observations for inference."""
    from datetime import datetime, timedelta, timezone

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
