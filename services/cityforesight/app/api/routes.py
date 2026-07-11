"""FastAPI route handlers."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException, Query

from app.config import settings
from app.data.lookup import lookup_at_point, search_by_address
from app.inference.predictor import predictor

router = APIRouter()


@router.get("/health")
def health():
    model_path = settings.artifacts_dir / "kil_lstm.pt"
    benchmark_path = settings.artifacts_dir / "benchmark.json"
    return {
        "status": "ok",
        "service": "cityforesight",
        "model_loaded": model_path.exists(),
        "benchmark_available": benchmark_path.exists(),
    }


@router.get("/forecasts/current")
def forecasts_current():
    return predictor.get_forecast(force_refresh=False)


@router.get("/forecasts/tract/{geoid}")
def forecast_tract(geoid: str):
    data = predictor.get_forecast()
    for feat in data["features"]["features"]:
        if feat["properties"].get("GEOID") == geoid:
            return {
                "geoid": geoid,
                "name": feat["properties"].get("NAME"),
                "forecasts": feat["properties"].get("forecasts", {}),
                "morphology": {
                    k: feat["properties"].get(k)
                    for k in (
                        "impervious_ratio",
                        "canopy_cover",
                        "drainage_capacity",
                        "population_density",
                    )
                },
                "last_updated": data["last_updated"],
            }
    raise HTTPException(status_code=404, detail=f"Tract {geoid} not found")


@router.get("/forecasts/search")
def forecast_search(q: str = Query(..., min_length=3)):
    query = q.strip()
    if len(query) < 3:
        raise HTTPException(status_code=400, detail="Search query is too short")
    try:
        result = search_by_address(query)
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Geocoding service unavailable") from None

    if result.get("candidates") is not None and not result.get("geoid"):
        if not result["candidates"]:
            raise HTTPException(
                status_code=404,
                detail="No matching address found within Travis County forecast coverage",
            )
        return result

    if not result or not result.get("geoid"):
        raise HTTPException(
            status_code=404,
            detail="Address is outside Travis County forecast coverage",
        )
    return result


@router.get("/forecasts/lookup")
def forecast_lookup(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    q: str | None = Query(default=None),
):
    result = lookup_at_point(lat, lon, query=q)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Address is outside Travis County forecast coverage",
        )
    return result


@router.get("/metrics/benchmark")
def metrics_benchmark():
    path = settings.artifacts_dir / "benchmark.json"
    if not path.exists():
        baseline_meta = settings.artifacts_dir / "baseline_meta.json"
        kil_meta = settings.artifacts_dir / "kil_meta.json"
        if baseline_meta.exists() and kil_meta.exists():
            b = json.loads(baseline_meta.read_text())
            k = json.loads(kil_meta.read_text())
            improvement = (b["val_rmse"] - k["val_rmse"]) / b["val_rmse"] * 100
            return {
                "baseline_rmse": b["val_rmse"],
                "kil_rmse": k["val_rmse"],
                "improvement_pct": round(improvement, 2),
                "gate_passed": improvement >= 15.0,
                "source": "validation_meta",
            }
        raise HTTPException(status_code=404, detail="Benchmark not yet computed. Run: npm run eval")
    return json.loads(path.read_text())


@router.post("/admin/refresh")
def admin_refresh(x_admin_token: str | None = Header(default=None)):
    if x_admin_token != settings.admin_token:
        raise HTTPException(status_code=401, detail="Invalid admin token")
    return predictor.get_forecast(force_refresh=True)
