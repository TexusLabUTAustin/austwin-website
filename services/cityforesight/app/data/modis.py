"""Stub for future NASA MODIS / Landsat LST tract labels."""

from __future__ import annotations


def lst_available() -> bool:
    """MODIS Earthdata auth pipeline not wired in this tranche."""
    return False


def note() -> str:
    return (
        "MODIS LST labels are deferred. CityForesight uses Open-Meteo temperature / "
        "soil temperature as a denser spatial weather prior instead."
    )
