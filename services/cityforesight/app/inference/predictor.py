"""Inference pipeline: ASOS → KIL LSTM → tract-level GeoJSON forecasts."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import torch

from app.config import settings
from app.data.asos import fetch_latest_obs, load_asos
from app.data.tracts import load_morphology_table, load_tract_geojson
from app.models.lstm import KILLSTM
from training.dataset import FEATURE_COLS

CACHE_FILE = "forecast_cache.json"
MORPH_COLS = [
    "impervious_ratio",
    "canopy_cover",
    "drainage_capacity",
    "population_density",
]


class ForecastPredictor:
    def __init__(self) -> None:
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model: KILLSTM | None = None
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
        self.model = KILLSTM(horizons=len(self.horizons), hidden_size=self.hidden_size).to(
            self.device
        )
        self.model.load_state_dict(ckpt["model_state"])
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

    @torch.no_grad()
    def predict(self) -> dict:
        if self.model is None:
            return self._fallback_forecast()

        weather = self._get_weather_window()
        x = self._normalize_row(weather)
        x_t = torch.from_numpy(x).unsqueeze(0).to(self.device)

        morphology = load_morphology_table()
        geojson = load_tract_geojson()
        morph_matrix = morphology[MORPH_COLS].values.astype(np.float32)
        morph_matrix = self._normalize_morph(morph_matrix)
        n_tracts = len(morph_matrix)
        x_batch = x_t.expand(n_tracts, -1, -1)
        morph_batch = torch.from_numpy(morph_matrix).to(self.device)

        forecasts_by_horizon: dict[str, list[float]] = {}
        features = copy.deepcopy(geojson)

        pred_all = self.model(x_batch, morph_batch)

        for h_idx, horizon in enumerate(self.horizons):
            tract_values = pred_all[:, h_idx].cpu().numpy().tolist()
            forecasts_by_horizon[str(horizon)] = tract_values

            for i, feat in enumerate(features["features"]):
                if h_idx == 0:
                    feat["properties"]["forecasts"] = {}
                feat["properties"]["forecasts"][str(horizon)] = round(tract_values[i], 2)

        result = {
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "station": settings.station_id,
            "horizons": self.horizons,
            "model": "kil_lstm",
            "features": features,
            "summary": {
                "min_heat_index": round(min(forecasts_by_horizon[str(self.horizons[0])]), 2),
                "max_heat_index": round(max(forecasts_by_horizon[str(self.horizons[-1])]), 2),
            },
        }
        self._write_cache(result)
        return result

    def _fallback_forecast(self) -> dict:
        weather = self._get_weather_window()
        base_hi = float(weather["heat_index"].iloc[-1])
        geojson = load_tract_geojson()
        morphology = load_morphology_table()
        features = copy.deepcopy(geojson)

        for i, feat in enumerate(features["features"]):
            morph = morphology.iloc[i]
            imp = morph["impervious_ratio"]
            canopy = morph["canopy_cover"]
            feat["properties"]["forecasts"] = {}
            for h in self.horizons:
                delta = 4.5 * (imp - 0.52) - 3.2 * (canopy - 0.28) + 0.3 * h
                feat["properties"]["forecasts"][str(h)] = round(base_hi + delta, 2)

        result = {
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "station": settings.station_id,
            "horizons": self.horizons,
            "model": "fallback_heuristic",
            "features": features,
            "summary": {"min_heat_index": base_hi - 5, "max_heat_index": base_hi + 8},
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
            if cached:
                return cached
        return self.predict()


predictor = ForecastPredictor()
