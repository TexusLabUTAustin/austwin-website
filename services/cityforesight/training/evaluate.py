#!/usr/bin/env python3
"""Evaluate baseline vs KIL on held-out set. Phase gate: >=15% heat RMSE improvement."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.data.asos import load_asos
from app.models.lstm import BaselineLSTM, KILLSTM
from training.dataset import BaselineEvalWrapper, WeatherSequenceDataset, train_val_test_split

GATE_IMPROVEMENT_PCT = 15.0


@torch.no_grad()
def tract_rmse(model, loader, device, kil: bool = False) -> tuple[float, list[float]]:
    model.eval()
    horizon_se = None
    n = 0
    for batch in loader:
        if kil:
            x, morph, y = batch[0], batch[1], batch[2]
            x, morph, y = x.to(device), morph.to(device), y.to(device)
            out = model(x, morph)
            pred = out[0] if isinstance(out, tuple) else out
        else:
            x, y = batch[0].to(device), batch[1].to(device)
            pred = model(x)
        se = ((pred - y) ** 2).sum(dim=0).cpu().numpy()
        horizon_se = se if horizon_se is None else horizon_se + se
        n += y.size(0)
    rmses = [float((h / n) ** 0.5) for h in horizon_se]
    return float(np.mean(rmses)), rmses


@torch.no_grad()
def multitask_rmse(model, loader, device) -> dict:
    model.eval()
    se = {"heat": 0.0, "flood": 0.0, "grid": 0.0}
    n = 0
    for batch in loader:
        x, morph, y, _sy, y_f, y_g = [b.to(device) for b in batch]
        heat, flood, grid = model(x, morph)
        se["heat"] += ((heat - y) ** 2).sum().item()
        se["flood"] += ((flood - y_f) ** 2).sum().item()
        se["grid"] += ((grid - y_g) ** 2).sum().item()
        n += y.numel()
    return {k: round((v / n) ** 0.5, 4) for k, v in se.items()}


def main() -> None:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    df = load_asos()
    df = df[df["valid"] >= "2020-01-01"].reset_index(drop=True)
    _, val_df, _ = train_val_test_split(df)

    kil_ds = WeatherSequenceDataset(
        val_df,
        lookback=settings.lookback_hours,
        use_kil=True,
        morph_samples=6,
        multitask=True,
    )
    baseline_ds = BaselineEvalWrapper(kil_ds)
    baseline_loader = DataLoader(baseline_ds, batch_size=256)
    kil_loader = DataLoader(kil_ds, batch_size=256)

    baseline_ckpt = torch.load(
        settings.artifacts_dir / "baseline_lstm.pt", map_location=device, weights_only=False
    )
    kil_ckpt = torch.load(
        settings.artifacts_dir / "kil_lstm.pt", map_location=device, weights_only=False
    )

    baseline = BaselineLSTM(
        horizons=len(settings.horizons),
        hidden_size=baseline_ckpt.get("hidden_size", 64),
        num_layers=baseline_ckpt.get("num_layers", 2),
    ).to(device)
    baseline.load_state_dict(baseline_ckpt["model_state"])
    multitask = bool(kil_ckpt.get("multitask", False)) or any(
        k.startswith("flood_head") for k in kil_ckpt["model_state"]
    )
    kil = KILLSTM(
        horizons=len(settings.horizons),
        hidden_size=kil_ckpt.get("hidden_size", 96),
        multitask=multitask,
    ).to(device)
    kil.load_state_dict(kil_ckpt["model_state"], strict=False)

    baseline_rmse, baseline_horizon = tract_rmse(baseline, baseline_loader, device, kil=False)
    kil_rmse, kil_horizon = tract_rmse(kil, kil_loader, device, kil=True)
    improvement = (baseline_rmse - kil_rmse) / baseline_rmse * 100.0

    result = {
        "metric": "tract_heat_index_rmse",
        "description": "Held-out validation: plain LSTM vs KIL heat; multitask reports flood/grid RMSE",
        "baseline_rmse": round(baseline_rmse, 4),
        "kil_rmse": round(kil_rmse, 4),
        "improvement_pct": round(improvement, 2),
        "gate_threshold_pct": GATE_IMPROVEMENT_PCT,
        "gate_passed": improvement >= GATE_IMPROVEMENT_PCT,
        "baseline_horizon_rmse": [round(r, 4) for r in baseline_horizon],
        "kil_horizon_rmse": [round(r, 4) for r in kil_horizon],
        "horizons_hours": settings.horizons,
        "multitask": multitask,
    }
    if multitask:
        result["kil_multitask_rmse"] = multitask_rmse(kil, kil_loader, device)

    (settings.artifacts_dir / "benchmark.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    if result["gate_passed"]:
        print(f"\n✓ Phase gate PASSED: {improvement:.1f}% improvement (>= {GATE_IMPROVEMENT_PCT}%)")
    else:
        print(f"\n✗ Phase gate NOT met: {improvement:.1f}% improvement (< {GATE_IMPROVEMENT_PCT}%)")
        sys.exit(1)


if __name__ == "__main__":
    main()
