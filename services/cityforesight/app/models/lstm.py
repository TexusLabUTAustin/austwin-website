"""PyTorch LSTM models for multi-hazard forecasting (heat / flood / grid)."""

from __future__ import annotations

import torch
import torch.nn as nn

WEATHER_FEATURES = 5  # tmpf, dwpf, sknt, drct, alti
MORPHOLOGY_FEATURES = 4  # impervious, canopy, drainage, pop_density
HAZARDS = ("heat", "flood", "grid")


class BaselineLSTM(nn.Module):
    """Two-layer LSTM → multi-horizon heat index forecast (phase-gate baseline)."""

    def __init__(
        self,
        input_size: int = WEATHER_FEATURES,
        hidden_size: int = 64,
        num_layers: int = 2,
        horizons: int = 6,
        dropout: float = 0.15,
    ):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size,
            hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self.head = nn.Sequential(
            nn.Linear(hidden_size, hidden_size),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size, horizons),
        )

    def encode(self, x: torch.Tensor) -> torch.Tensor:
        _, (h_n, _) = self.lstm(x)
        return h_n[-1]

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.head(self.encode(x))


class KILLSTM(nn.Module):
    """KIL multi-task: shared weather encoder + heat residual + flood/grid heads."""

    def __init__(
        self,
        input_size: int = WEATHER_FEATURES,
        morph_size: int = MORPHOLOGY_FEATURES,
        hidden_size: int = 64,
        num_layers: int = 2,
        horizons: int = 6,
        dropout: float = 0.15,
        multitask: bool = True,
    ):
        super().__init__()
        self.multitask = multitask
        self.horizons = horizons
        self.lstm = nn.LSTM(
            input_size,
            hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self.weather_head = nn.Sequential(
            nn.Linear(hidden_size, hidden_size),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size, horizons),
        )
        self.kil_head = nn.Sequential(
            nn.Linear(hidden_size + morph_size, hidden_size),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size, horizons),
        )
        if multitask:
            self.flood_head = nn.Sequential(
                nn.Linear(hidden_size + morph_size, hidden_size),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(hidden_size, horizons),
            )
            self.grid_head = nn.Sequential(
                nn.Linear(hidden_size + morph_size, hidden_size),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(hidden_size, horizons),
            )

    def encode(self, x: torch.Tensor) -> torch.Tensor:
        _, (h_n, _) = self.lstm(x)
        return h_n[-1]

    def forward(
        self,
        x: torch.Tensor,
        morph: torch.Tensor,
        return_parts: bool = False,
    ):
        h = self.encode(x)
        base = self.weather_head(h)
        delta = self.kil_head(torch.cat([h, morph], dim=-1))
        heat = base + delta

        if not self.multitask or not hasattr(self, "flood_head"):
            if return_parts:
                return heat, None, None, base, delta
            return heat

        hm = torch.cat([h, morph], dim=-1)
        flood = torch.sigmoid(self.flood_head(hm)) * 100.0
        grid = torch.sigmoid(self.grid_head(hm)) * 100.0
        if return_parts:
            return heat, flood, grid, base, delta
        return heat, flood, grid
