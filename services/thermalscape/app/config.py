from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ENV_FILE = _REPO_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="THERMALSCAPE_",
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    artifacts_dir: Path = Path(__file__).resolve().parents[1] / "artifacts"


settings = Settings()
settings.artifacts_dir.mkdir(parents=True, exist_ok=True)
