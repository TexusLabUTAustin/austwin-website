"""UrbanSense FastAPI application."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.inference.detector import detector
from app.inference.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        detector.get_anomalies(force_refresh=True)
    except Exception:
        pass
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="AusTwin UrbanSense",
    description="Tract-level heat anomaly detection with urban climate ontology",
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
