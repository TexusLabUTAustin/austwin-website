"""PyTorch LSTM models for heat index forecasting."""

from __future__ import annotations

import torch
import torch.nn as nn

WEATHER_FEATURES = 5  # tmpf, dwpf, sknt, drct, alti
MORPHOLOGY_FEATURES = 4  # impervious, canopy, drainage, pop_density


class BaselineLSTM(nn.Module):
    """Two-layer LSTM → multi-horizon heat index forecast."""

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
    """KIL variant: weather base forecast + morphology residual (SmartPilot-style KIL)."""

    def __init__(
        self,
        input_size: int = WEATHER_FEATURES,
        morph_size: int = MORPHOLOGY_FEATURES,
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

    def encode(self, x: torch.Tensor) -> torch.Tensor:
        _, (h_n, _) = self.lstm(x)
        return h_n[-1]

    def forward(self, x: torch.Tensor, morph: torch.Tensor) -> torch.Tensor:
        h = self.encode(x)
        base = self.weather_head(h)
        delta = self.kil_head(torch.cat([h, morph], dim=-1))
        return base + delta
