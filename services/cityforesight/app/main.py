"""CityForesight FastAPI application."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.inference.predictor import predictor
from app.inference.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(_app: FastAPI):
    predictor.get_forecast(force_refresh=True)
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="AusTwin CityForesight",
    description="1–6 hour heat index forecasting with KIL morphology features",
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
