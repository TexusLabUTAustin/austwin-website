"""CityGuide API — grounded operator Q&A."""

from __future__ import annotations

import re

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.agent.loop import run_agent
from app.clients import systemdata
from app.config import settings
from app.llm import engine
from app.rag import store

router = APIRouter()

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Query intents that warrant pulling live system data.
FORECAST_WORDS = {
    "hot", "hottest", "forecast", "forecasts", "now", "current", "currently",
    "heat", "temperature", "temp", "risk", "tract", "tracts", "warm", "warmest",
    "cool", "coolest", "today", "tonight", "degrees", "index", "hours", "horizon",
}
ANOMALY_WORDS = {
    "anomaly", "anomalies", "alert", "alerts", "watch", "extreme", "spike",
    "spikes", "unusual", "abnormal", "severity", "warning", "warnings", "flagged",
}

SYSTEM_PROMPT = (
    "You are CityGuide, the operator Q&A copilot for AusTwin — Austin's open-source "
    "urban climate digital twin. Answer ONLY from the provided context, which is a mix "
    "of live system data and a curated knowledge base. Be concise, specific, and "
    "operational. When you use a fact, say which source it came from. If the context does "
    "not contain the answer, say you don't have that information — never invent numbers, "
    "tract names, thresholds, or protocols. NWS heat-index bands: 80-90F Caution, "
    "90-103F Extreme Caution, 103-124F Danger, 125F+ Extreme Danger."
)

REFUSAL = (
    "I don't have grounded information to answer that confidently, so I won't guess. "
    "I can help with: current heat-index forecasts and hottest tracts, active heat "
    "anomalies/alerts, metric definitions (impervious ratio, tree canopy, drainage), "
    "how the forecasting and anomaly models work, and Austin heat-response protocols."
)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    horizon: int = Field(default=1, ge=1, le=6)


class Source(BaseModel):
    type: str  # "live" | "doc"
    title: str


class ChatResponse(BaseModel):
    answer: str
    grounded: bool
    refused: bool
    used_live: list[str]
    sources: list[Source]
    model: str


@router.get("/health")
def health():
    live = systemdata.health()
    return {
        "status": "ok",
        "service": "cityguide",
        "llm_loaded": engine.llm_available(),
        "llm_error": engine.load_error(),
        "cityforesight_reachable": live["cityforesight"],
        "urbansense_reachable": live["urbansense"],
    }


def _extractive_answer(query: str, live_blocks: list[str], retrieved) -> str:
    """Fallback when the LLM isn't available: return grounded context directly."""
    parts: list[str] = []
    if live_blocks:
        parts.extend(live_blocks)
    for r in retrieved[:2]:
        if r.cosine >= settings.retrieval_threshold:
            parts.append(r.chunk.text)
    if not parts:
        return REFUSAL
    return (
        "LLM not loaded — showing the grounded source material for your question:\n\n"
        + "\n\n".join(parts)
    )


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    query = req.message.strip()

    # Preferred path: tool-calling agent (fetches live data + KB on demand,
    # chains tools for complex questions).
    if engine.llm_available():
        try:
            result = run_agent(query)
            sources = [Source(type="live", title=s) for s in result["live_used"]]
            sources += [Source(type="doc", title=f"tool: {t}") for t in result["tools_used"]]
            return ChatResponse(
                answer=result["answer"],
                grounded=not result["refused"],
                refused=result["refused"],
                used_live=result["live_used"],
                sources=sources,
                model=f"{settings.model_file} · agent",
            )
        except Exception:  # noqa: BLE001
            pass  # fall through to extractive RAG

    # Fallback path (no LLM): single-shot retrieval + live snapshots.
    tokens = set(_TOKEN_RE.findall(query.lower()))
    live_blocks: list[str] = []
    used_live: list[str] = []
    sources: list[Source] = []

    if tokens & FORECAST_WORDS:
        snap = systemdata.forecast_snapshot(req.horizon)
        if snap:
            live_blocks.append(snap)
            used_live.append("CityForesight forecast")
            sources.append(Source(type="live", title="CityForesight live forecast"))
    if tokens & ANOMALY_WORDS:
        snap = systemdata.anomaly_snapshot()
        if snap:
            live_blocks.append(snap)
            used_live.append("UrbanSense anomalies")
            sources.append(Source(type="live", title="UrbanSense live anomalies"))

    retrieved, max_cos = store.retrieve(query)
    doc_hits = [r for r in retrieved if r.cosine >= settings.retrieval_threshold]
    for r in doc_hits:
        sources.append(Source(type="doc", title=f"{r.chunk.doc}: {r.chunk.title}"))

    grounded = bool(live_blocks) or max_cos >= settings.retrieval_threshold
    if not grounded:
        return ChatResponse(
            answer=REFUSAL, grounded=False, refused=True,
            used_live=[], sources=[], model="guardrail",
        )

    context_parts = list(live_blocks)
    context_parts.extend(f"[{r.chunk.doc}: {r.chunk.title}]\n{r.chunk.text}" for r in doc_hits)
    context = "\n\n".join(context_parts)

    if engine.llm_available():
        user = (
            f"Context:\n{context}\n\n"
            f"Question: {query}\n\n"
            "Answer using only the context above. Cite the source(s) you used. "
            "If the context is insufficient, say so plainly."
        )
        try:
            answer = engine.generate(SYSTEM_PROMPT, user)
            model = settings.model_file
        except Exception:  # noqa: BLE001
            answer = _extractive_answer(query, live_blocks, retrieved)
            model = "extractive-fallback"
    else:
        answer = _extractive_answer(query, live_blocks, retrieved)
        model = "extractive-fallback"

    return ChatResponse(
        answer=answer, grounded=True, refused=False,
        used_live=used_live, sources=sources, model=model,
    )
