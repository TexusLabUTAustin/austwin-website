#!/usr/bin/env python3
"""Seed static urban climate ontology from tract morphology."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.data.tracts import load_morphology_table
from app.ontology.model import save_graph, seed_static_ontology


def main() -> None:
    morph = load_morphology_table()
    g = seed_static_ontology(morph, settings.station_id)
    save_graph(g)
    print(f"Ontology seeded: {len(morph)} tracts → {settings.ontology_dir / 'austwin.ttl'}")


if __name__ == "__main__":
    main()
