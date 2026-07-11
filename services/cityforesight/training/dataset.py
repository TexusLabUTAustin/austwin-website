"""Training dataset builders for baseline and KIL models."""

from __future__ import annotations

import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset

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


class WeatherSequenceDataset(Dataset):
    def __init__(
        self,
        df: pd.DataFrame,
        lookback: int = 24,
        horizons: list[int] | None = None,
        use_kil: bool = False,
        morph_samples: int = 4,
    ):
        self.lookback = lookback
        self.horizons = horizons or HORIZONS
        self.use_kil = use_kil
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

        norm_df, self.stats = normalize_features(df)
        valid = norm_df[FEATURE_COLS + ["heat_index"]].notna().all(axis=1)
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
            for h in self.horizons:
                station_hi = self.heat_index[seq_idx + h]
                base_targets.append(tract_heat_adjustment(morph_row, float(station_hi)))
            y = np.array(base_targets, dtype=np.float32)
            station_y = np.array(
                [self.heat_index[seq_idx + h] for h in self.horizons],
                dtype=np.float32,
            )
            return (
                torch.from_numpy(x),
                torch.from_numpy(morph),
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
    """Expose KIL tract targets for baseline evaluation (no morphology input)."""

    def __init__(self, kil_ds: WeatherSequenceDataset):
        self.kil_ds = kil_ds

    def __len__(self) -> int:
        return len(self.kil_ds)

    def __getitem__(self, idx: int):
        x, _morph, y, _station_y = self.kil_ds[idx]
        return x, y
