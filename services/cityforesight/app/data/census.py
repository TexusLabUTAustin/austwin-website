"""Census ACS population data for Travis County tracts."""

from __future__ import annotations

import logging

import requests

logger = logging.getLogger(__name__)

CENSUS_ACS_URL = "https://api.census.gov/data/2022/acs/acs5"
TRAVIS_STATE_FIPS = "48"
TRAVIS_COUNTY_FIPS = "453"


def fetch_tract_population(api_key: str) -> dict[str, int]:
    """Fetch 2022 ACS 5-year population (B01003) per census tract in Travis County."""
    params = {
        "get": "NAME,B01003_001E",
        "for": "tract:*",
        "in": f"state:{TRAVIS_STATE_FIPS} county:{TRAVIS_COUNTY_FIPS}",
        "key": api_key,
    }
    resp = requests.get(CENSUS_ACS_URL, params=params, timeout=120)
    resp.raise_for_status()
    rows = resp.json()
    header, *data = rows
    name_idx = header.index("NAME")
    pop_idx = header.index("B01003_001E")
    state_idx = header.index("state")
    county_idx = header.index("county")
    tract_idx = header.index("tract")

    out: dict[str, int] = {}
    for row in data:
        geoid = f"{row[state_idx]}{row[county_idx]}{row[tract_idx]}"
        try:
            pop = int(row[pop_idx])
        except (TypeError, ValueError):
            continue
        if pop >= 0:
            out[geoid] = pop
    logger.info("Fetched ACS population for %d Travis County tracts", len(out))
    return out


def uniform_population_density(aland_m2: dict[str, float], county_pop: int = 1_305_000) -> dict[str, float]:
    """Estimate tract population density when ACS API key is unavailable.

    Distributes a Travis County population estimate by land area share.
    """
    total_land = sum(aland_m2.values())
    if total_land <= 0:
        return {geoid: 0.0 for geoid in aland_m2}
    return {
        geoid: (county_pop * (land / total_land)) / (land / 1_000_000.0)
        for geoid, land in aland_m2.items()
        if land > 0
    }
