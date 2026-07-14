from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ENV_FILE = _REPO_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="URBANSENSE_",
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    data_dir: Path = _REPO_ROOT / "data"
    artifacts_dir: Path = Path(__file__).resolve().parents[1] / "artifacts"
    ontology_dir: Path = _REPO_ROOT / "data" / "ontology"
    cityforesight_url: str = "http://localhost:8000"
    station_id: str = "KAUS"
    default_horizon: int = 1
    horizons: list[int] = [1, 2, 3, 4, 5, 6]
    refresh_interval_minutes: int = 15
    admin_token: str = "dev-admin-token"
    anomaly_event_retention_days: int = 7


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.artifacts_dir.mkdir(parents=True, exist_ok=True)
settings.ontology_dir.mkdir(parents=True, exist_ok=True)
