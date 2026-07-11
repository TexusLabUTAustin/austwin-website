from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ENV_FILE = _REPO_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CITYGUIDE_",
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Live system data sources (grounding).
    cityforesight_url: str = "http://localhost:8000"
    urbansense_url: str = "http://localhost:8001"

    # Local open-source LLM (llama.cpp, GGUF pulled from Hugging Face). $0, offline.
    model_repo: str = "Qwen/Qwen2.5-3B-Instruct-GGUF"
    model_file: str = "qwen2.5-3b-instruct-q4_k_m.gguf"
    n_ctx: int = 4096
    n_threads: int = 0  # 0 → llama.cpp auto
    n_gpu_layers: int = -1  # -1 → offload all to Metal/GPU when available
    max_tokens: int = 512
    temperature: float = 0.2

    # Retrieval (local embeddings — sentence-transformers, free).
    embed_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    top_k: int = 4
    # Below this cosine similarity (and with no live data) → refuse, no hallucination.
    retrieval_threshold: float = 0.28

    admin_token: str = "dev-admin-token"

    # External climate feeds (Open-Meteo + NWS) — free, no key.
    austin_lat: float = 30.27
    austin_lon: float = -97.74
    nws_user_agent: str = "AusTwin-CityGuide (contact@austwin.org)"


settings = Settings()
