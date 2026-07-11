"""RAG over the local knowledge base.

Neural retrieval (sentence-transformers cosine) fused with symbolic retrieval
(Jaccard token overlap) — mirrors the proposal's BERT-cosine + Jaccard design.
Embeddings run locally and free; sentence-transformers is imported lazily so the
service boots without it installed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.config import settings

KB_DIR = Path(__file__).resolve().parents[1] / "knowledge"
_TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass
class Chunk:
    doc: str
    title: str
    text: str


_model = None
_chunks: list[Chunk] = []
_embeds: np.ndarray | None = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(settings.embed_model)
    return _model


def _split(md: str) -> list[tuple[str, str]]:
    """Split a markdown doc into (heading, body) chunks."""
    parts = re.split(r"\n(?=#{1,6}\s)", md.strip())
    out: list[tuple[str, str]] = []
    for part in parts:
        block = part.strip()
        if not block:
            continue
        first = block.splitlines()[0]
        title = first.lstrip("#").strip() if first.startswith("#") else "General"
        out.append((title, block))
    return out


def load() -> None:
    """Load + embed the KB once (idempotent)."""
    global _chunks, _embeds
    if _embeds is not None:
        return
    _chunks = []
    for path in sorted(KB_DIR.glob("*.md")):
        for title, body in _split(path.read_text()):
            _chunks.append(Chunk(doc=path.stem, title=title, text=body))
    if not _chunks:
        _embeds = np.zeros((0, 384), dtype=np.float32)
        return
    model = _get_model()
    _embeds = np.asarray(
        model.encode([c.text for c in _chunks], normalize_embeddings=True),
        dtype=np.float32,
    )


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


def _jaccard(a: str, b: str) -> float:
    sa, sb = _tokens(a), _tokens(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


@dataclass
class Retrieved:
    chunk: Chunk
    score: float
    cosine: float


def retrieve(query: str) -> tuple[list[Retrieved], float]:
    """Return top-k chunks (fused score) and the best cosine similarity seen."""
    load()
    if not _chunks:
        return [], 0.0
    model = _get_model()
    q = np.asarray(model.encode([query], normalize_embeddings=True)[0], dtype=np.float32)
    cos = _embeds @ q  # both normalized → cosine similarity
    results: list[Retrieved] = []
    for i, chunk in enumerate(_chunks):
        c = float(cos[i])
        fused = 0.7 * c + 0.3 * _jaccard(query, chunk.text)
        results.append(Retrieved(chunk=chunk, score=fused, cosine=c))
    results.sort(key=lambda r: r.score, reverse=True)
    max_cos = max((r.cosine for r in results), default=0.0)
    return results[: settings.top_k], max_cos
