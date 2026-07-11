"""Tests for census tract point lookup."""

from __future__ import annotations

import pytest

from app.data.tracts import tract_at_point


@pytest.mark.parametrize(
    "lat,lon",
    [
        (30.2747, -97.7404),  # Texas State Capitol
        (30.2672, -97.7431),  # Downtown Austin
    ],
)
def test_tract_at_point_inside_travis(lat: float, lon: float) -> None:
    result = tract_at_point(lat, lon)
    assert result is not None
    assert result["geoid"]
    assert result["name"]


def test_tract_at_point_outside_coverage() -> None:
    # Houston — outside Travis County tract polygons
    assert tract_at_point(29.7604, -95.3698) is None
