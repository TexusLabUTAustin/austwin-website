#!/usr/bin/env python3
"""Phase 2 gate: synthetic hotspot injection anomaly detection test."""

from __future__ import annotations

import copy
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.data.tracts import load_morphology_table, load_tract_geojson
from app.detection.engine import compute_tract_anomalies
from app.ontology.model import append_anomaly_events, new_graph, seed_static_ontology

GATE_PRECISION = 0.80
HOTSPOT_DELTA_F = 12.0
N_INJECT = 5


def main() -> None:
    morphology = load_morphology_table()
    geojson = load_tract_geojson()
    features = geojson["features"]
    rng = random.Random(42)
    injected = set(rng.sample(range(len(features)), min(N_INJECT, len(features))))

    mock_forecast = {
        "model": "mock",
        "features": {
            "features": copy.deepcopy(features),
        },
    }
    city_median = 88.0
    for i, feat in enumerate(mock_forecast["features"]["features"]):
        base = city_median + HOTSPOT_DELTA_F if i in injected else city_median
        feat["properties"]["forecasts"] = {str(h): round(base, 2) for h in range(1, 7)}

    scores = compute_tract_anomalies(mock_forecast, morphology, horizon=1)
    injected_geoids = {features[i]["properties"]["GEOID"] for i in injected}
    hits = sum(
        1
        for s in scores
        if s["geoid"] in injected_geoids and s["severity"] in ("alert", "extreme")
    )
    precision = hits / len(injected_geoids) if injected_geoids else 0.0

    g = seed_static_ontology(morphology)
    flagged = [s for s in scores if s["geoid"] in injected_geoids]
    append_anomaly_events(g, flagged, horizon=1, observed_hi=90.0)
    anomaly_triples = sum(1 for _ in g.triples((None, None, None)) if "anomaly" in str(_[0]))

    passed = precision >= GATE_PRECISION and anomaly_triples > 0
    result = {
        "metric": "synthetic_hotspot_detection",
        "injected_tracts": len(injected_geoids),
        "hits_alert_or_extreme": hits,
        "precision": round(precision, 4),
        "gate_threshold": GATE_PRECISION,
        "gate_passed": passed,
        "ontology_anomaly_triples": anomaly_triples,
    }
    out = settings.artifacts_dir / "anomaly_benchmark.json"
    out.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    if not passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
