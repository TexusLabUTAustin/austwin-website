"""Serialize RDF graphs to JSON-LD."""

from __future__ import annotations

import json

from rdflib import Graph


def graph_to_jsonld(g: Graph) -> list | dict:
    raw = g.serialize(format="json-ld")
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    return json.loads(raw)
