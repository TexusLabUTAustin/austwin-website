"""Inference pipeline: ASOS → multi-task KIL → tract GeoJSON (heat/flood/grid + confidence)."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests
import torch

from app.config import settings
from app.data.asos import fetch_latest_obs, load_asos
from app.data.ercot import fetch_load_factor
from app.data.hazard_proxies import (
    confidence_from_delta,
    flood_risk_from_obs,
    grid_stress_from_obs,
    score_confidence,
)
from app.data.openmeteo import recent_precip_inches
from app.data.usgs_gauges import fetch_gauge_snapshot, local_gauge_stress
from app.data.tracts import load_morphology_table, load_tract_geojson
from app.models.lstm import HAZARDS, KILLSTM
from training.dataset import FEATURE_COLS

CACHE_FILE = "forecast_cache.json"
MORPH_COLS = [
    "impervious_ratio",
    "canopy_cover",
    "drainage_capacity",
    "population_density",
]


def _feature_centroid(feat: dict) -> tuple[float, float] | None:
    geom = feat.get("geometry") or {}
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if not coords:
        return None

    def _avg(points: list) -> tuple[float, float]:
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        return sum(ys) / len(ys), sum(xs) / len(xs)  # lat, lon

    try:
        if gtype == "Polygon":
            return _avg(coords[0])
        if gtype == "MultiPolygon":
            return _avg(coords[0][0])
        if gtype == "Point":
            return float(coords[1]), float(coords[0])
    except Exception:
        return None
    return None



class ForecastPredictor:
    def __init__(self) -> None:
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model: KILLSTM | None = None
        self.multitask = False
        self.feature_stats: dict | None = None
        self.morph_mean: np.ndarray | None = None
        self.morph_std: np.ndarray | None = None
        self.lookback = settings.lookback_hours
        self.horizons = settings.horizons
        self.hidden_size = 96
        self._load_model()

    def _load_model(self) -> None:
        ckpt_path = settings.artifacts_dir / "kil_lstm.pt"
        if not ckpt_path.exists():
            return
        ckpt = torch.load(ckpt_path, map_location=self.device, weights_only=False)
        self.hidden_size = ckpt.get("hidden_size", 96)
        state = ckpt["model_state"]
        self.multitask = bool(ckpt.get("multitask", False)) or any(
            k.startswith("flood_head") for k in state
        )
        self.model = KILLSTM(
            horizons=len(self.horizons),
            hidden_size=self.hidden_size,
            multitask=self.multitask,
        ).to(self.device)
        self.model.load_state_dict(state, strict=False)
        self.model.eval()
        self.feature_stats = ckpt["feature_stats"]
        self.lookback = ckpt.get("lookback", self.lookback)
        if "morph_mean" in ckpt:
            self.morph_mean = np.array(ckpt["morph_mean"], dtype=np.float32)
            self.morph_std = np.array(ckpt["morph_std"], dtype=np.float32)

    def _normalize_morph(self, morph_matrix: np.ndarray) -> np.ndarray:
        if self.morph_mean is not None and self.morph_std is not None:
            return (morph_matrix - self.morph_mean) / self.morph_std
        return morph_matrix

    def _normalize_row(self, df: pd.DataFrame) -> np.ndarray:
        assert self.feature_stats is not None
        cols = []
        for col in FEATURE_COLS:
            mean = self.feature_stats[col]["mean"]
            std = self.feature_stats[col]["std"] or 1.0
            cols.append(((df[col].ffill().bfill().values - mean) / std).astype(np.float32))
        return np.stack(cols, axis=-1)

    def _get_weather_window(self) -> pd.DataFrame:
        try:
            recent = fetch_latest_obs(station=settings.station_id, hours=self.lookback + 2)
            if len(recent) >= self.lookback:
                return recent.tail(self.lookback)
        except Exception:
            pass
        historical = load_asos()
        return historical.tail(self.lookback)

    def _enrich_anomalies(self, features: dict) -> None:
        if not settings.anomaly_enrich:
            return
        url = settings.urbansense_url.rstrip("/") + "/anomalies/current"
        try:
            resp = requests.get(url, timeout=4)
            if not resp.ok:
                return
            data = resp.json()
        except Exception:
            return

        by_geoid: dict[str, dict] = {}
        for feat in data.get("features", {}).get("features", []):
            props = feat.get("properties") or {}
            gid = props.get("GEOID") or props.get("geoid")
            if gid:
                by_geoid[str(gid)] = props

        for feat in features["features"]:
            props = feat["properties"]
            gid = str(props.get("GEOID", ""))
            anom = by_geoid.get(gid)
            if not anom:
                continue
            severity = anom.get("severity") or "normal"
            score = float(anom.get("anomaly_score") or 0.0)
            props["anomaly_severity"] = severity
            props["anomaly_score"] = round(score, 3)

            if severity in ("alert", "extreme") and "forecasts" in props:
                bump = 1.2 if severity == "alert" else 2.0
                for h, v in list(props["forecasts"].items()):
                    props["forecasts"][h] = round(float(v) + bump, 2)
                conf = props.get("confidence") or {}
                heat_c = conf.get("heat") or {}
                for h, c in list(heat_c.items()):
                    heat_c[h] = round(max(0.35, float(c) - (0.12 if severity == "alert" else 0.2)), 3)
                conf["heat"] = heat_c
                props["confidence"] = conf

    @torch.no_grad()
    def predict(self) -> dict:
        if self.model is None:
            return self._fallback_forecast()

        weather = self._get_weather_window()
        x = self._normalize_row(weather)
        x_t = torch.from_numpy(x).unsqueeze(0).to(self.device)

        morphology = load_morphology_table()
        geojson = load_tract_geojson()
        morph_raw = morphology[MORPH_COLS].values.astype(np.float32)
        morph_norm = self._normalize_morph(morph_raw.copy())
        n_tracts = len(morph_norm)
        x_batch = x_t.expand(n_tracts, -1, -1)
        morph_batch = torch.from_numpy(morph_norm).to(self.device)

        features = copy.deepcopy(geojson)
        precip = recent_precip_inches(6)
        load_info = fetch_load_factor()
        load_factor = load_info.get("load_factor")
        gauge_snap = fetch_gauge_snapshot()

        out = self.model(x_batch, morph_batch, return_parts=True)
        heat, _flood_m, _grid_m, base, delta = out

        heat_np = heat.cpu().numpy()
        delta_np = delta.cpu().numpy()

        heat_vals_h0: list[float] = []
        flood_vals_h0: list[float] = []
        grid_vals_h0: list[float] = []

        for i, feat in enumerate(features["features"]):
            props = feat["properties"]
            props["forecasts"] = {}
            props["flood_forecasts"] = {}
            props["grid_forecasts"] = {}
            props["confidence"] = {"heat": {}, "flood": {}, "grid": {}}

            morph_row = morphology.iloc[i]
            latlon = _feature_centroid(feat)
            g_stress = (
                local_gauge_stress(latlon[0], latlon[1], gauge_snap)
                if latlon
                else float(gauge_snap.get("city_flood_factor") or 0.0)
            )

            for h_idx, horizon in enumerate(self.horizons):
                h_key = str(horizon)
                hi = float(heat_np[i, h_idx])
                props["forecasts"][h_key] = round(hi, 2)
                dlt = float(delta_np[i, h_idx])
                props["confidence"]["heat"][h_key] = round(
                    confidence_from_delta(dlt, horizon), 3
                )

                # Horizon adds mild lag for ongoing precip / stage persistence
                precip_h = precip * (1.0 + 0.08 * (horizon - 1))
                fl = flood_risk_from_obs(
                    precip_h,
                    g_stress,
                    impervious=float(morph_row["impervious_ratio"]),
                    drainage=float(morph_row["drainage_capacity"]),
                )
                gd = grid_stress_from_obs(
                    hi,
                    float(load_factor) if load_factor is not None else None,
                    float(morph_row["population_density"]),
                    demand_mw=load_info.get("demand_mw"),
                    capacity_mw=load_info.get("capacity_mw"),
                )
                if gd != gd:  # NaN — ERCOT unavailable
                    gd = 0.0

                props["flood_forecasts"][h_key] = round(fl, 2)
                props["grid_forecasts"][h_key] = round(gd, 2)
                props["confidence"]["flood"][h_key] = round(
                    score_confidence(fl, horizon, base=0.88 if gauge_snap.get("gauges") else 0.7),
                    3,
                )
                props["confidence"]["grid"][h_key] = round(
                    score_confidence(gd, horizon, base=0.9 if load_factor is not None else 0.55),
                    3,
                )

                if h_idx == 0:
                    heat_vals_h0.append(hi)
                    flood_vals_h0.append(fl)
                    grid_vals_h0.append(gd)

        self._enrich_anomalies(features)

        heat_all = []
        flood_all = []
        grid_all = []
        for feat in features["features"]:
            p = feat["properties"]
            heat_all.extend(p["forecasts"].values())
            flood_all.extend(p["flood_forecasts"].values())
            grid_all.extend(p["grid_forecasts"].values())

        result = {
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "station": settings.station_id,
            "horizons": self.horizons,
            "hazards": list(HAZARDS),
            "model": "kil_lstm_multitask" if self.multitask else "kil_lstm",
            "features": features,
            "inputs": self._inputs_payload(precip, load_info, gauge_snap),
            "summary": {
                "min_heat_index": round(min(heat_all), 2) if heat_all else None,
                "max_heat_index": round(max(heat_all), 2) if heat_all else None,
                "heat": {
                    "min": round(min(heat_vals_h0), 2) if heat_vals_h0 else None,
                    "max": round(max(heat_vals_h0), 2) if heat_vals_h0 else None,
                },
                "flood": {
                    "min": round(min(flood_vals_h0), 2) if flood_vals_h0 else None,
                    "max": round(max(flood_vals_h0), 2) if flood_vals_h0 else None,
                },
                "grid": {
                    "min": round(min(grid_vals_h0), 2) if grid_vals_h0 else None,
                    "max": round(max(grid_vals_h0), 2) if grid_vals_h0 else None,
                },
            },
        }
        self._write_cache(result)
        return result

    def _inputs_payload(self, precip: float, load_info: dict, gauge_snap: dict) -> dict:
        top_gauges = sorted(
            gauge_snap.get("gauges") or [],
            key=lambda g: g.get("stress") or 0,
            reverse=True,
        )[:4]
        return {
            "precip_in_6h": round(precip, 3),
            "precip_source": "open-meteo",
            "ercot_load_factor": load_info.get("load_factor"),
            "ercot_demand_mw": load_info.get("demand_mw"),
            "ercot_capacity_mw": load_info.get("capacity_mw"),
            "ercot_reserve_mw": load_info.get("reserve_mw"),
            "ercot_utilization_pct": load_info.get("utilization_pct"),
            "ercot_source": load_info.get("source"),
            "ercot_timestamp": load_info.get("timestamp") or load_info.get("last_updated"),
            "usgs_source": gauge_snap.get("source"),
            "usgs_gauge_count": gauge_snap.get("gauge_count"),
            "usgs_city_flood_factor": gauge_snap.get("city_flood_factor"),
            "usgs_top_gauges": [
                {
                    "site": g.get("site"),
                    "name": g.get("name"),
                    "gage_height_ft": g.get("gage_height_ft"),
                    "discharge_cfs": g.get("discharge_cfs"),
                    "stress": g.get("stress"),
                }
                for g in top_gauges
            ],
        }

    def _fallback_forecast(self) -> dict:
        weather = self._get_weather_window()
        base_hi = float(weather["heat_index"].iloc[-1])
        geojson = load_tract_geojson()
        morphology = load_morphology_table()
        features = copy.deepcopy(geojson)
        precip = recent_precip_inches(6)
        load_info = fetch_load_factor()
        load_factor = load_info.get("load_factor")
        gauge_snap = fetch_gauge_snapshot()

        heat_vals: list[float] = []
        flood_vals: list[float] = []
        grid_vals: list[float] = []

        for i, feat in enumerate(features["features"]):
            morph = morphology.iloc[i]
            imp = morph["impervious_ratio"]
            canopy = morph["canopy_cover"]
            props = feat["properties"]
            props["forecasts"] = {}
            props["flood_forecasts"] = {}
            props["grid_forecasts"] = {}
            props["confidence"] = {"heat": {}, "flood": {}, "grid": {}}
            latlon = _feature_centroid(feat)
            g_stress = (
                local_gauge_stress(latlon[0], latlon[1], gauge_snap)
                if latlon
                else float(gauge_snap.get("city_flood_factor") or 0.0)
            )
            for h in self.horizons:
                delta = 4.5 * (imp - 0.52) - 3.2 * (canopy - 0.28) + 0.3 * h
                hi = base_hi + delta
                fl = flood_risk_from_obs(
                    precip * (1.0 + 0.08 * (h - 1)),
                    g_stress,
                    impervious=float(imp),
                    drainage=float(morph["drainage_capacity"]),
                )
                gd = grid_stress_from_obs(
                    hi,
                    float(load_factor) if load_factor is not None else None,
                    float(morph["population_density"]),
                    demand_mw=load_info.get("demand_mw"),
                    capacity_mw=load_info.get("capacity_mw"),
                )
                if gd != gd:
                    gd = 0.0
                props["forecasts"][str(h)] = round(hi, 2)
                props["flood_forecasts"][str(h)] = round(fl, 2)
                props["grid_forecasts"][str(h)] = round(gd, 2)
                props["confidence"]["heat"][str(h)] = round(
                    confidence_from_delta(delta, h), 3
                )
                props["confidence"]["flood"][str(h)] = round(score_confidence(fl, h), 3)
                props["confidence"]["grid"][str(h)] = round(score_confidence(gd, h), 3)
                if h == self.horizons[0]:
                    heat_vals.append(hi)
                    flood_vals.append(fl)
                    grid_vals.append(gd)

        self._enrich_anomalies(features)

        result = {
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "station": settings.station_id,
            "horizons": self.horizons,
            "hazards": list(HAZARDS),
            "model": "fallback_heuristic",
            "features": features,
            "inputs": self._inputs_payload(precip, load_info, gauge_snap),
            "summary": {
                "min_heat_index": round(min(heat_vals), 2) if heat_vals else base_hi - 5,
                "max_heat_index": round(max(heat_vals), 2) if heat_vals else base_hi + 8,
                "heat": {
                    "min": round(min(heat_vals), 2) if heat_vals else None,
                    "max": round(max(heat_vals), 2) if heat_vals else None,
                },
                "flood": {
                    "min": round(min(flood_vals), 2) if flood_vals else None,
                    "max": round(max(flood_vals), 2) if flood_vals else None,
                },
                "grid": {
                    "min": round(min(grid_vals), 2) if grid_vals else None,
                    "max": round(max(grid_vals), 2) if grid_vals else None,
                },
            },
        }
        self._write_cache(result)
        return result

    def _write_cache(self, payload: dict) -> None:
        cache_path = settings.artifacts_dir / CACHE_FILE
        cache_path.write_text(json.dumps(payload))

    def load_cache(self) -> dict | None:
        cache_path = settings.artifacts_dir / CACHE_FILE
        if not cache_path.exists():
            return None
        return json.loads(cache_path.read_text())

    def get_forecast(self, force_refresh: bool = False) -> dict:
        if not force_refresh:
            cached = self.load_cache()
            if (
                cached
                and cached.get("inputs", {}).get("usgs_source")
                and "flood_forecasts"
                in ((cached.get("features") or {}).get("features") or [{}])[0].get(
                    "properties", {}
                )
            ):
                return cached
        return self.predict()


predictor = ForecastPredictor()
