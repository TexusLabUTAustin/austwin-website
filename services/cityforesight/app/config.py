from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ENV_FILE = _REPO_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CITYFORESIGHT_",
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    data_dir: Path = _REPO_ROOT / "data"
    artifacts_dir: Path = Path(__file__).resolve().parents[1] / "artifacts"
    station_id: str = "KAUS"
    lookback_hours: int = 24
    horizons: list[int] = [1, 2, 3, 4, 5, 6]
    refresh_interval_minutes: int = 15
    admin_token: str = "dev-admin-token"
    census_api_key: str = Field(default="", validation_alias="CENSUS_API_KEY")
    fetch_nlcd: bool = True
    geocode_user_agent: str = "AusTwin-CityForesight/0.1"
    # west, south, east, north — Travis County / Austin metro bias for Nominatim
    geocode_viewbox_west: float = -98.2
    geocode_viewbox_south: float = 30.0
    geocode_viewbox_east: float = -97.3
    geocode_viewbox_north: float = 30.6


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.artifacts_dir.mkdir(parents=True, exist_ok=True)
(processed := settings.data_dir / "processed").mkdir(parents=True, exist_ok=True)
