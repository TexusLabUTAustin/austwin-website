"""UrbanSense API routes."""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import PlainTextResponse

from app.clients import cityforesight as cf_client
from app.config import settings
from app.inference.detector import detector
from app.ontology.export import graph_to_jsonld
from app.ontology.model import TTL_PATH, load_graph, subgraph_for_tract, tract_uri

router = APIRouter()


@router.get("/health")
def health():
    cf_ok = cf_client.check_cityforesight_health()
    return {
        "status": "ok" if cf_ok else "degraded",
        "service": "urbansense",
        "cityforesight_reachable": cf_ok,
        "ontology_available": TTL_PATH.exists(),
    }


@router.get("/anomalies/current")
def anomalies_current():
    return detector.get_anomalies(force_refresh=False)


@router.get("/anomalies/tract/{geoid}")
def anomaly_tract(geoid: str):
    detail = detector.get_tract_detail(geoid)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Tract {geoid} not found")
    return detail


@router.get("/ontology/tract/{geoid}")
def ontology_tract(geoid: str):
    if not TTL_PATH.exists():
        raise HTTPException(status_code=404, detail="Ontology not built. Run: npm run ontology:build")
    g = load_graph()
    t = tract_uri(geoid)
    if not any(g.triples((t, None, None))):
        raise HTTPException(status_code=404, detail=f"Tract {geoid} not in ontology")
    sub = subgraph_for_tract(g, geoid)
    return graph_to_jsonld(sub)


@router.get("/ontology/export.ttl")
def ontology_export_ttl():
    if not TTL_PATH.exists():
        raise HTTPException(status_code=404, detail="Ontology not built")
    return PlainTextResponse(TTL_PATH.read_text(), media_type="text/turtle")


@router.post("/admin/refresh")
def admin_refresh(x_admin_token: str | None = Header(default=None)):
    if x_admin_token != settings.admin_token:
        raise HTTPException(status_code=401, detail="Invalid admin token")
    return detector.get_anomalies(force_refresh=True)
