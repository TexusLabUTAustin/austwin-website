"""CityGuide FastAPI application — operator Q&A copilot."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.llm import engine
from app.rag import store


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Warm retrieval (fast) synchronously; warm the LLM in the background so the
    # first request isn't blocked on the one-time model download / load.
    try:
        store.load()
    except Exception:  # noqa: BLE001
        pass
    engine.warm()
    yield


app = FastAPI(
    title="AusTwin CityGuide",
    description="Operator Q&A grounded on live system data + knowledge base (local LLM + RAG)",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
