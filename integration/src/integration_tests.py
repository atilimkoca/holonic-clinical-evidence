"""Pytest smoke tests for the group integration layer."""
from __future__ import annotations

import sys
from pathlib import Path

from rdflib import Graph, URIRef
from rdflib.namespace import RDF

REPO = Path(__file__).resolve().parents[2]
SRC = Path(__file__).resolve().parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from end_to_end_pipeline import (  # noqa: E402
    HOLON_CLASS,
    build_shared_integration_test_set,
    run_pipeline,
    selected_holon_files,
    validate_holons,
)


def test_project1_holon_parseable():
    graph = Graph().parse(selected_holon_files(1)[0], format="turtle")
    assert any(graph.subjects(RDF.type, URIRef(HOLON_CLASS)))


def test_shared_integration_test_set_has_20_holons():
    path = build_shared_integration_test_set(20)
    graph = Graph().parse(path, format="turtle")
    holons = list(graph.subjects(RDF.type, URIRef(HOLON_CLASS)))
    assert len(holons) == 20


def test_project2_validates_sample_holons():
    summary = validate_holons(3)
    assert summary["sample_size"] == 3
    assert summary["conforming_holons"] == 3


def test_end_to_end_pipeline_smoke():
    result = run_pipeline(sample_size=3)
    assert result["shared_test_set_holons"] == 20
    assert result["validation"]["conforming_holons"] == 3
    assert result["query"]["backend"] in {"rdflib", "neo4j"}
    assert result["generation"]["converged"] is True
    assert result["generation"]["hallucination_rate"] == 0.0
