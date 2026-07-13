"""Training dataset builders for baseline and multi-task KIL models."""

from __future__ import annotations

import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset

from app.data.hazard_proxies import (
    flood_risk_score,
    grid_stress_score,
)
from app.data.tracts import load_morphology_table, tract_heat_adjustment
from app.models.lstm import MORPHOLOGY_FEATURES, WEATHER_FEATURES

FEATURE_COLS = ["tmpf", "dwpf", "sknt", "drct", "alti"]
HORIZONS = [1, 2, 3, 4, 5, 6]


def normalize_features(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    stats = {}
    out = df.copy()
    for col in FEATURE_COLS:
        out[col] = out[col].ffill().bfill()
        mean = float(out[col].mean())
        std = float(out[col].std()) or 1.0
        stats[col] = {"mean": mean, "std": std}
        out[col] = (out[col] - mean) / std
    out["heat_index"] = out["heat_index"].ffill().bfill()
    return out, stats


def _ensure_precip(df: pd.DataFrame) -> pd.Series:
    for col in ("p01i", "p01in", "precip"):
        if col in df.columns:
            return pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    return pd.Series(np.zeros(len(df)), index=df.index)


class WeatherSequenceDataset(Dataset):
    def __init__(
        self,
        df: pd.DataFrame,
        lookback: int = 24,
        horizons: list[int] | None = None,
        use_kil: bool = False,
        morph_samples: int = 4,
        multitask: bool = False,
    ):
        self.lookback = lookback
        self.horizons = horizons or HORIZONS
        self.use_kil = use_kil
        self.multitask = multitask and use_kil
        self.morph_samples = morph_samples
        self.morphology = load_morphology_table() if use_kil else None
        self.morph_matrix = (
            self.morphology[
                ["impervious_ratio", "canopy_cover", "drainage_capacity", "population_density"]
            ].values.astype(np.float32)
            if use_kil
            else None
        )
        if use_kil and self.morph_matrix is not None:
            self.morph_mean = self.morph_matrix.mean(axis=0)
            self.morph_std = self.morph_matrix.std(axis=0) + 1e-6

        # Precip before normalize (raw df)
        self.precip_raw = _ensure_precip(df).values.astype(np.float32)
        self.hour_utc = (
            pd.to_datetime(df["valid"], utc=True).dt.hour.values
            if "valid" in df.columns
            else np.zeros(len(df), dtype=np.int32)
        )

        norm_df, self.stats = normalize_features(df)
        valid = norm_df[FEATURE_COLS + ["heat_index"]].notna().all(axis=1)
        # Align precip/hour with filtered rows
        self.precip_raw = self.precip_raw[valid.values]
        self.hour_utc = self.hour_utc[valid.values]
        norm_df = norm_df.loc[valid].reset_index(drop=True)
        self.values = norm_df[FEATURE_COLS].values.astype(np.float32)
        self.heat_index = norm_df["heat_index"].values.astype(np.float32)

        self.indices: list[int] = []
        max_h = max(self.horizons)
        for i in range(lookback, len(self.values) - max_h):
            self.indices.append(i)

    def __len__(self) -> int:
        mult = self.morph_samples if self.use_kil else 1
        return len(self.indices) * mult

    def _base_index(self, idx: int) -> tuple[int, int | None]:
        if not self.use_kil:
            return self.indices[idx], None
        seq_idx = self.indices[idx // self.morph_samples]
        morph_pick = (seq_idx * self.morph_samples + (idx % self.morph_samples)) % len(
            self.morph_matrix
        )
        return seq_idx, morph_pick

    def __getitem__(self, idx: int):
        seq_idx, morph_idx = self._base_index(idx)
        x = self.values[seq_idx - self.lookback : seq_idx]

        if self.use_kil and morph_idx is not None:
            morph = self.morph_matrix[morph_idx]
            morph = (morph - self.morph_mean) / self.morph_std
            morph_row = self.morphology.iloc[morph_idx]
            base_targets = []
            flood_targets = []
            grid_targets = []
            for h in self.horizons:
                station_hi = float(self.heat_index[seq_idx + h])
                base_targets.append(tract_heat_adjustment(morph_row, station_hi))
                if self.multitask:
                    start = max(0, seq_idx + h - 2)
                    precip = float(self.precip_raw[start : seq_idx + h + 1].sum())
                    flood_targets.append(
                        flood_risk_score(
                            precip,
                            float(morph_row["impervious_ratio"]),
                            float(morph_row["drainage_capacity"]),
                            float(morph_row["canopy_cover"]),
                        )
                    )
                    grid_targets.append(
                        grid_stress_score(
                            station_hi,
                            float(morph_row["population_density"]),
                            load_factor=None,
                            hour_utc=int(self.hour_utc[min(seq_idx + h, len(self.hour_utc) - 1)]),
                        )
                    )
            y = np.array(base_targets, dtype=np.float32)
            station_y = np.array(
                [self.heat_index[seq_idx + h] for h in self.horizons],
                dtype=np.float32,
            )
            if self.multitask:
                return (
                    torch.from_numpy(x),
                    torch.from_numpy(morph.astype(np.float32)),
                    torch.from_numpy(y),
                    torch.from_numpy(station_y),
                    torch.from_numpy(np.array(flood_targets, dtype=np.float32)),
                    torch.from_numpy(np.array(grid_targets, dtype=np.float32)),
                )
            return (
                torch.from_numpy(x),
                torch.from_numpy(morph.astype(np.float32)),
                torch.from_numpy(y),
                torch.from_numpy(station_y),
            )

        y = np.array(
            [self.heat_index[seq_idx + h] for h in self.horizons],
            dtype=np.float32,
        )
        return torch.from_numpy(x), torch.from_numpy(y)


def train_val_test_split(
    df: pd.DataFrame, train_frac: float = 0.7, val_frac: float = 0.15
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    n = len(df)
    train_end = int(n * train_frac)
    val_end = int(n * (train_frac + val_frac))
    return df.iloc[:train_end], df.iloc[train_end:val_end], df.iloc[val_end:]


class BaselineEvalWrapper(Dataset):
    """Expose KIL tract heat targets for baseline evaluation (no morphology input)."""

    def __init__(self, kil_ds: WeatherSequenceDataset):
        self.kil_ds = kil_ds

    def __len__(self) -> int:
        return len(self.kil_ds)

    def __getitem__(self, idx: int):
        item = self.kil_ds[idx]
        # x, morph, y_heat, station_y[, flood, grid]
        return item[0], item[2]
