"""Local open-source LLM via llama.cpp. GGUF weights pulled from Hugging Face.

Zero API cost, zero tokens, fully offline after the one-time model download.
Heavy imports are lazy so the service boots even before llama-cpp-python or the
model weights are present — chat then degrades to an extractive answer.
"""

from __future__ import annotations

import threading

from app.config import settings

_llm = None
_load_error: str | None = None
_lock = threading.Lock()


def _get_llm():
    global _llm, _load_error
    if _llm is not None or _load_error is not None:
        return _llm
    with _lock:
        if _llm is None and _load_error is None:
            try:
                from llama_cpp import Llama

                kwargs = dict(
                    repo_id=settings.model_repo,
                    filename=settings.model_file,
                    n_ctx=settings.n_ctx,
                    n_gpu_layers=settings.n_gpu_layers,
                    verbose=False,
                )
                if settings.n_threads:
                    kwargs["n_threads"] = settings.n_threads
                _llm = Llama.from_pretrained(**kwargs)
            except Exception as exc:  # noqa: BLE001
                _load_error = f"{type(exc).__name__}: {exc}"
    return _llm


def llm_available() -> bool:
    return _get_llm() is not None


def load_error() -> str | None:
    return _load_error


def warm() -> None:
    """Trigger model load in the background (best-effort)."""
    threading.Thread(target=_get_llm, daemon=True).start()


def generate(system: str, user: str, max_tokens: int | None = None) -> str:
    return chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        max_tokens=max_tokens,
    )


def chat(
    messages: list[dict],
    *,
    response_format: dict | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> str:
    """Multi-turn completion. Optional response_format (e.g. JSON schema) for tools."""
    llm = _get_llm()
    if llm is None:
        raise RuntimeError(_load_error or "LLM unavailable")
    kwargs: dict = dict(
        messages=messages,
        max_tokens=max_tokens or settings.max_tokens,
        temperature=settings.temperature if temperature is None else temperature,
    )
    if response_format is not None:
        kwargs["response_format"] = response_format
    out = llm.create_chat_completion(**kwargs)
    return (out["choices"][0]["message"].get("content") or "").strip()
