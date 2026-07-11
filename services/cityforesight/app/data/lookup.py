"""Build address search / point lookup responses from forecast cache."""

from __future__ import annotations

from app.data.geocode import GeocodeResult, geocode_query
from app.data.tracts import tract_at_point
from app.inference.predictor import predictor

COVERAGE_NOTE = (
    "Neighborhood estimate for this census tract — not a reading at your exact address."
)


def _tract_forecast_payload(
    geoid: str,
    *,
    query: str | None = None,
    matched_address: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
) -> dict | None:
    data = predictor.get_forecast()
    for feat in data["features"]["features"]:
        if feat["properties"].get("GEOID") != geoid:
            continue
        props = feat["properties"]
        return {
            "query": query,
            "matched_address": matched_address,
            "lat": lat,
            "lon": lon,
            "geoid": geoid,
            "name": props.get("NAME"),
            "forecasts": props.get("forecasts", {}),
            "morphology": {
                k: props.get(k)
                for k in (
                    "impervious_ratio",
                    "canopy_cover",
                    "drainage_capacity",
                    "population_density",
                )
            },
            "last_updated": data["last_updated"],
            "coverage_note": COVERAGE_NOTE,
        }
    return None


def lookup_at_point(
    lat: float,
    lon: float,
    *,
    query: str | None = None,
    matched_address: str | None = None,
) -> dict | None:
    tract = tract_at_point(lat, lon)
    if tract is None:
        return None
    return _tract_forecast_payload(
        tract["geoid"],
        query=query,
        matched_address=matched_address or f"{lat:.5f}, {lon:.5f}",
        lat=lat,
        lon=lon,
    )


def search_by_address(query: str) -> dict:
    """
    Geocode query and resolve to tract forecast.
    Returns either a full result dict or { candidates: [...] } for disambiguation.
    """
    try:
        geocoded = geocode_query(query)
    except RuntimeError:
        raise

    in_coverage: list[GeocodeResult] = []
    for hit in geocoded:
        if tract_at_point(hit.lat, hit.lon) is not None:
            in_coverage.append(hit)

    if not in_coverage:
        return {"candidates": []}

    if len(in_coverage) == 1:
        hit = in_coverage[0]
        result = lookup_at_point(
            hit.lat,
            hit.lon,
            query=query,
            matched_address=hit.display_name,
        )
        return result or {"candidates": []}

    candidates = [
        {
            "matched_address": hit.display_name,
            "lat": hit.lat,
            "lon": hit.lon,
        }
        for hit in in_coverage
    ]
    return {"query": query, "candidates": candidates}
