#!/usr/bin/env python3
"""Train multi-task KIL LSTM (heat + flood + grid heads)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.data.asos import load_asos
from app.models.lstm import KILLSTM
from training.dataset import WeatherSequenceDataset, train_val_test_split

LOOKBACK = settings.lookback_hours
HORIZONS = len(settings.horizons)
EPOCHS = 12
BATCH_SIZE = 512
LR = 1e-3


def train_epoch(model, loader, optimizer, criterion, device):
    model.train()
    total = 0.0
    for batch in loader:
        x, morph, y, station_y, y_flood, y_grid = [b.to(device) for b in batch]
        optimizer.zero_grad()
        heat, flood, grid, base, delta = model(x, morph, return_parts=True)
        delta_true = y - station_y
        loss = (
            criterion(heat, y)
            + 0.5 * criterion(delta, delta_true)
            + 0.35 * criterion(flood, y_flood)
            + 0.35 * criterion(grid, y_grid)
        )
        loss.backward()
        optimizer.step()
        total += loss.item() * x.size(0)
    return total / len(loader.dataset)


@torch.no_grad()
def eval_rmse(model, loader, device):
    model.eval()
    se_h = se_f = se_g = 0.0
    n = 0
    for batch in loader:
        x, morph, y, _station_y, y_flood, y_grid = [b.to(device) for b in batch]
        heat, flood, grid = model(x, morph)
        se_h += ((heat - y) ** 2).sum().item()
        se_f += ((flood - y_flood) ** 2).sum().item()
        se_g += ((grid - y_grid) ** 2).sum().item()
        n += y.numel()
    return {
        "heat": (se_h / n) ** 0.5,
        "flood": (se_f / n) ** 0.5,
        "grid": (se_g / n) ** 0.5,
    }


def main() -> None:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    df = load_asos()
    df = df[df["valid"] >= "2020-01-01"].reset_index(drop=True)
    train_df, val_df, _ = train_val_test_split(df)

    train_ds = WeatherSequenceDataset(
        train_df, lookback=LOOKBACK, use_kil=True, morph_samples=6, multitask=True
    )
    val_ds = WeatherSequenceDataset(
        val_df, lookback=LOOKBACK, use_kil=True, morph_samples=6, multitask=True
    )
    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE)

    model = KILLSTM(horizons=HORIZONS, hidden_size=96, num_layers=2, multitask=True).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=LR)
    criterion = nn.MSELoss()
    best_rmse = float("inf")

    for epoch in range(1, EPOCHS + 1):
        loss = train_epoch(model, train_loader, optimizer, criterion, device)
        rmses = eval_rmse(model, val_loader, device)
        if rmses["heat"] < best_rmse:
            best_rmse = rmses["heat"]
            torch.save(
                {
                    "model_state": model.state_dict(),
                    "feature_stats": train_ds.stats,
                    "morph_mean": train_ds.morph_mean.tolist(),
                    "morph_std": train_ds.morph_std.tolist(),
                    "lookback": LOOKBACK,
                    "horizons": settings.horizons,
                    "hidden_size": 96,
                    "multitask": True,
                },
                settings.artifacts_dir / "kil_lstm.pt",
            )
        if epoch % 4 == 0:
            print(
                f"Epoch {epoch}: loss={loss:.4f} "
                f"heat_rmse={rmses['heat']:.4f} "
                f"flood_rmse={rmses['flood']:.4f} "
                f"grid_rmse={rmses['grid']:.4f}"
            )

    meta = {"val_rmse": best_rmse, "model": "kil_lstm", "multitask": True}
    (settings.artifacts_dir / "kil_meta.json").write_text(json.dumps(meta, indent=2))
    print(f"KIL multi-task training complete. Best heat val RMSE: {best_rmse:.4f}")


if __name__ == "__main__":
    main()
