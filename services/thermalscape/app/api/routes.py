"""Thermalscape API — serves the precomputed street-level UTCI tile."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from app.config import settings
from app.data.utci_raster import full_payload, load_meta, sample_at

router = APIRouter()


def _meta_path():
    return settings.artifacts_dir / "utci.json"


def _png_path():
    return settings.artifacts_dir / "utci.png"


@router.get("/health")
def health():
    return {
        "status": "ok",
        "service": "thermalscape",
        "tile_available": _meta_path().exists() and _png_path().exists(),
    }


@router.get("/utci")
def utci():
    """Overlay metadata, summary stats, legend scale, and PNG URL."""
    if not _meta_path().exists() or not _png_path().exists():
        if not load_meta():
            raise HTTPException(
                status_code=404,
                detail="No UTCI tile yet. Run: python services/thermalscape/scripts/build_tile.py",
            )
    return full_payload()


@router.get("/utci/sample")
def utci_sample(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
):
    result = sample_at(lat, lon)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="No UTCI value at this location (outside tile or nodata).",
        )
    return result


@router.get("/utci.png")
def utci_png():
    p = _png_path()
    if not p.exists():
        raise HTTPException(status_code=404, detail="No UTCI tile rendered yet.")
    return FileResponse(p, media_type="image/png")
