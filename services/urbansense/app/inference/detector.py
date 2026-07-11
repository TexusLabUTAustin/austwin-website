"""Anomaly detection pipeline: forecast → score → cache → ontology."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone

from app.clients import cityforesight as cf_client
from app.config import settings
from app.data.asos import latest_observed_heat_index
from app.data.tracts import load_morphology_table, load_tract_geojson
from app.detection.engine import compute_tract_anomalies
from app.ontology.model import (
    append_anomaly_events,
    load_graph,
    save_graph,
    seed_static_ontology,
    subgraph_for_tract,
)

CACHE_FILE = "anomaly_cache.json"


class AnomalyDetector:
    def __init__(self) -> None:
        self.horizon = settings.default_horizon

    def detect(self, *, forecast_payload: dict | None = None) -> dict:
        morphology = load_morphology_table()
        geojson = load_tract_geojson()

        if forecast_payload is None:
            forecast_payload = cf_client.fetch_current_forecast()

        scores = compute_tract_anomalies(
            forecast_payload, morphology, horizon=self.horizon
        )
        score_by_geoid = {s["geoid"]: s for s in scores}
        observed_hi = latest_observed_heat_index()

        features = copy.deepcopy(geojson)
        for feat in features["features"]:
            geoid = feat["properties"].get("GEOID", "")
            anomaly = score_by_geoid.get(geoid, {})
            feat["properties"].update(anomaly)

        result = {
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "station": settings.station_id,
            "horizon": self.horizon,
            "horizons": settings.horizons,
            "cityforesight_model": forecast_payload.get("model", "unknown"),
            "features": features,
            "summary": {
                "watch": sum(1 for s in scores if s["severity"] == "watch"),
                "alert": sum(1 for s in scores if s["severity"] == "alert"),
                "extreme": sum(1 for s in scores if s["severity"] == "extreme"),
                "max_score": max((s["anomaly_score"] for s in scores), default=0),
            },
        }

        self._update_ontology(scores, observed_hi)
        self._write_cache(result)
        return result

    def _update_ontology(self, scores: list[dict], observed_hi: float) -> None:
        morphology = load_morphology_table()
        if not (settings.ontology_dir / "austwin.ttl").exists():
            g = seed_static_ontology(morphology, settings.station_id)
        else:
            g = load_graph()
        flagged = [s for s in scores if s["severity"] != "normal"]
        append_anomaly_events(g, flagged or scores[:5], horizon=self.horizon, observed_hi=observed_hi)
        save_graph(g)

    def _write_cache(self, payload: dict) -> None:
        path = settings.artifacts_dir / CACHE_FILE
        path.write_text(json.dumps(payload))

    def load_cache(self) -> dict | None:
        path = settings.artifacts_dir / CACHE_FILE
        if not path.exists():
            return None
        return json.loads(path.read_text())

    def get_anomalies(self, *, force_refresh: bool = False) -> dict:
        if not force_refresh:
            cached = self.load_cache()
            if cached:
                return cached
        return self.detect()

    def get_tract_detail(self, geoid: str) -> dict | None:
        data = self.get_anomalies()
        for feat in data["features"]["features"]:
            if feat["properties"].get("GEOID") == geoid:
                g = load_graph()
                sub = subgraph_for_tract(g, geoid)
                from app.ontology.export import graph_to_jsonld

                return {
                    "geoid": geoid,
                    "name": feat["properties"].get("NAME"),
                    "anomaly": {
                        k: feat["properties"].get(k)
                        for k in (
                            "anomaly_score",
                            "severity",
                            "horizon",
                            "tract_forecast",
                            "city_median",
                            "observed_heat_index",
                            "factors",
                        )
                    },
                    "last_updated": data["last_updated"],
                    "ontology": graph_to_jsonld(sub),
                }
        return None


detector = AnomalyDetector()
