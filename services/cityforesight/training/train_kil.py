#!/usr/bin/env python3
"""Train KIL LSTM with morphology feature injection."""

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
        x, morph, y, station_y = batch
        x, morph, y, station_y = (
            x.to(device),
            morph.to(device),
            y.to(device),
            station_y.to(device),
        )
        optimizer.zero_grad()
        h = model.encode(x)
        base = model.weather_head(h)
        delta = model.kil_head(torch.cat([h, morph], dim=-1))
        pred = base + delta
        delta_true = y - station_y
        loss = criterion(pred, y) + 0.5 * criterion(delta, delta_true)
        loss.backward()
        optimizer.step()
        total += loss.item() * x.size(0)
    return total / len(loader.dataset)


@torch.no_grad()
def eval_rmse(model, loader, device):
    model.eval()
    se = 0.0
    n = 0
    for batch in loader:
        x, morph, y = batch[0].to(device), batch[1].to(device), batch[2].to(device)
        pred = model(x, morph)
        se += ((pred - y) ** 2).sum().item()
        n += y.numel()
    return (se / n) ** 0.5


def main() -> None:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    df = load_asos()
    df = df[df["valid"] >= "2020-01-01"].reset_index(drop=True)
    train_df, val_df, _ = train_val_test_split(df)

    train_ds = WeatherSequenceDataset(train_df, lookback=LOOKBACK, use_kil=True, morph_samples=6)
    val_ds = WeatherSequenceDataset(val_df, lookback=LOOKBACK, use_kil=True, morph_samples=6)
    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE)

    model = KILLSTM(horizons=HORIZONS, hidden_size=96, num_layers=2).to(device)
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
                    "morph_mean": train_ds.morph_mean.tolist(),
                    "morph_std": train_ds.morph_std.tolist(),
                    "lookback": LOOKBACK,
                    "horizons": settings.horizons,
                    "hidden_size": 96,
                },
                settings.artifacts_dir / "kil_lstm.pt",
            )
        if epoch % 4 == 0:
            print(f"Epoch {epoch}: loss={loss:.4f} val_rmse={rmse:.4f}")

    meta = {"val_rmse": best_rmse, "model": "kil_lstm"}
    (settings.artifacts_dir / "kil_meta.json").write_text(json.dumps(meta, indent=2))
    print(f"KIL training complete. Best val RMSE: {best_rmse:.4f}")


if __name__ == "__main__":
    main()
