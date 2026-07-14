#!/usr/bin/env python3
"""Train baseline LSTM heat index model."""

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
from app.models.lstm import BaselineLSTM
from training.dataset import WeatherSequenceDataset, train_val_test_split

LOOKBACK = settings.lookback_hours
HORIZONS = len(settings.horizons)
EPOCHS = 10
BATCH_SIZE = 256
LR = 8e-4


def train_epoch(model, loader, optimizer, criterion, device):
    model.train()
    total = 0.0
    n = 0
    for batch in loader:
        x, y = batch[0].to(device), batch[1].to(device)
        optimizer.zero_grad()
        pred = model(x)
        loss = criterion(pred, y)
        loss.backward()
        optimizer.step()
        total += loss.item() * x.size(0)
        n += x.size(0)
    return total / max(n, 1)


@torch.no_grad()
def eval_rmse(model, loader, device):
    model.eval()
    se = 0.0
    n = 0
    for batch in loader:
        x, y = batch[0].to(device), batch[1].to(device)
        pred = model(x)
        se += ((pred - y) ** 2).sum().item()
        n += y.numel()
    return (se / n) ** 0.5


def main() -> None:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    df = load_asos()
    df = df[df["valid"] >= "2020-01-01"].reset_index(drop=True)
    train_df, val_df, _ = train_val_test_split(df)

    train_ds = WeatherSequenceDataset(train_df, lookback=LOOKBACK, use_kil=False)
    val_ds = WeatherSequenceDataset(val_df, lookback=LOOKBACK, use_kil=False)
    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE)

    model = BaselineLSTM(horizons=HORIZONS, hidden_size=64, num_layers=2).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=LR)
    criterion = nn.MSELoss()
    best_rmse = float("inf")

    for epoch in range(1, EPOCHS + 1):
        loss = train_epoch(model, train_loader, optimizer, criterion, device)
        rmse = eval_rmse(model, val_loader, device)
        if rmse < best_rmse:
            best_rmse = rmse
            torch.save(
                {
                    "model_state": model.state_dict(),
                    "feature_stats": train_ds.stats,
                    "lookback": LOOKBACK,
                    "horizons": settings.horizons,
                    "hidden_size": 64,
                    "num_layers": 2,
                },
                settings.artifacts_dir / "baseline_lstm.pt",
            )
        if epoch % 5 == 0:
            print(f"Epoch {epoch}: loss={loss:.4f} val_rmse={rmse:.4f}")

    meta = {"val_rmse": best_rmse, "model": "baseline_lstm"}
    (settings.artifacts_dir / "baseline_meta.json").write_text(json.dumps(meta, indent=2))
    print(f"Baseline training complete. Best val RMSE: {best_rmse:.4f}")


if __name__ == "__main__":
    main()
