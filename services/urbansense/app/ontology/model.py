"""RDFLib urban climate ontology (SOSA-inspired, file-backed)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, XSD

from app.config import settings

AUSTWIN = Namespace("https://austwin.org/ontology#")
SOSA = Namespace("http://www.w3.org/ns/sosa/")

TTL_PATH = settings.ontology_dir / "austwin.ttl"
JSONLD_PATH = settings.ontology_dir / "austwin.jsonld"


def new_graph() -> Graph:
    g = Graph()
    g.bind("austwin", AUSTWIN)
    g.bind("sosa", SOSA)
    g.bind("rdfs", RDFS)
    return g


def load_graph() -> Graph:
    g = new_graph()
    if TTL_PATH.exists():
        g.parse(TTL_PATH, format="turtle")
    return g


def save_graph(g: Graph) -> None:
    TTL_PATH.parent.mkdir(parents=True, exist_ok=True)
    g.serialize(destination=TTL_PATH, format="turtle")
    from app.ontology.export import graph_to_jsonld

    JSONLD_PATH.write_text(json.dumps(graph_to_jsonld(g), indent=2))


def tract_uri(geoid: str) -> URIRef:
    return URIRef(f"https://austwin.org/tract/{geoid}")


def station_uri(station_id: str) -> URIRef:
    return URIRef(f"https://austwin.org/station/{station_id}")


def seed_static_ontology(morphology: pd.DataFrame, station_id: str = "KAUS") -> Graph:
    """Seed tract and morphology triples from CSV."""
    g = new_graph()
    st = station_uri(station_id)
    g.add((st, RDF.type, AUSTWIN.WeatherStation))
    g.add((st, RDFS.label, Literal(station_id)))

    for _, row in morphology.iterrows():
        geoid = str(row["geoid"])
        t = tract_uri(geoid)
        g.add((t, RDF.type, AUSTWIN.Tract))
        g.add((t, RDFS.label, Literal(str(row.get("name", geoid)))))
        g.add((t, AUSTWIN.geoid, Literal(geoid)))
        g.add((t, AUSTWIN.imperviousRatio, Literal(float(row["impervious_ratio"]), datatype=XSD.float)))
        g.add((t, AUSTWIN.canopyCover, Literal(float(row["canopy_cover"]), datatype=XSD.float)))
        g.add((t, AUSTWIN.drainageCapacity, Literal(float(row["drainage_capacity"]), datatype=XSD.float)))
        g.add((t, AUSTWIN.populationDensity, Literal(float(row["population_density"]), datatype=XSD.float)))
        g.add((t, AUSTWIN.observedAt, st))

        profile = URIRef(f"https://austwin.org/morphology/{geoid}")
        g.add((profile, RDF.type, AUSTWIN.MorphologyProfile))
        g.add((t, AUSTWIN.hasMorphology, profile))

    return g


def append_anomaly_events(
    g: Graph,
    anomalies: list[dict[str, Any]],
    *,
    horizon: int,
    observed_hi: float,
) -> Graph:
    """Add forecast and anomaly event triples for flagged tracts."""
    now = datetime.now(timezone.utc).isoformat()
    for row in anomalies:
        geoid = row["geoid"]
        t = tract_uri(geoid)
        event_id = uuid4().hex[:12]
        event = URIRef(f"https://austwin.org/anomaly/{geoid}/{event_id}")

        forecast = URIRef(f"https://austwin.org/forecast/{geoid}/{event_id}")
        g.add((forecast, RDF.type, AUSTWIN.Forecast))
        g.add((forecast, AUSTWIN.heatIndex, Literal(row["tract_forecast"], datatype=XSD.float)))
        g.add((forecast, AUSTWIN.horizonHours, Literal(horizon, datatype=XSD.integer)))
        g.add((t, AUSTWIN.hasForecast, forecast))

        obs = URIRef(f"https://austwin.org/observation/{settings.station_id}/{event_id}")
        g.add((obs, RDF.type, SOSA.Observation))
        g.add((obs, SOSA.madeBySensor, station_uri(settings.station_id)))
        g.add((obs, SOSA.hasResult, Literal(observed_hi, datatype=XSD.float)))
        g.add((obs, SOSA.phenomenonTime, Literal(now, datatype=XSD.dateTime)))

        if row["severity"] in ("watch", "alert", "extreme"):
            g.add((event, RDF.type, AUSTWIN.AnomalyEvent))
            g.add((event, AUSTWIN.anomalyScore, Literal(row["anomaly_score"], datatype=XSD.float)))
            g.add((event, AUSTWIN.severity, Literal(row["severity"])))
            g.add((event, SOSA.phenomenonTime, Literal(now, datatype=XSD.dateTime)))
            g.add((t, AUSTWIN.hasAnomaly, event))

    return g


def subgraph_for_tract(g: Graph, geoid: str) -> Graph:
    """Extract triples related to a tract."""
    t = tract_uri(geoid)
    sub = new_graph()
    for s, p, o in g.triples((t, None, None)):
        sub.add((s, p, o))
    for s, p, o in g.triples((None, None, t)):
        sub.add((s, p, o))
    for s, p, o in g:
        if str(geoid) in str(s) or str(geoid) in str(o):
            sub.add((s, p, o))
    return sub
