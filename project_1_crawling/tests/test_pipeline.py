"""Test suite for Project 1 — the holonic data layer.

Covers the graded claims: minimum data volume, determinism (fixed seed), dual-model
construction, the information-preservation bijection, the >=15% expressiveness
gain, holon-level topology / homomorphism, and the Project 2 SHACL integration.

Run from the repo root:  python -m pytest project_1_crawling/tests -q
The crawl step is offline (cached); no network is required.
"""
from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

import pytest

from project_1_crawling.src import (config as C, entity_extractor, rdf_transformer,
                                    benchmark, graph_analysis)


@pytest.fixture(scope="session", autouse=True)
def built():
    """Regenerate processed data + both RDF models once for the session."""
    entity_extractor.extract()
    rdf_transformer.transform()
    yield


# --- data volume (assignment minimums) ---------------------------------------
def test_minimum_data_volume():
    stats = json.loads((C.PROCESSED_DIR / "extract_stats.json").read_text("utf-8"))
    assert stats["n_holons"] >= 200, "need >= 200 clinical-question holons"
    assert stats["n_entities_total"] >= 500, "need >= 500 unique entities"


def test_entity_and_relation_types():
    g_stats = json.loads((C.RESULTS_DIR / "model_stats.json").read_text("utf-8"))
    assert g_stats["model_a"]["triples"] >= 1500, "need >= 1500 holonic triples"


def test_determinism_seed():
    """Re-running extraction with the fixed seed yields byte-identical holons."""
    first = (C.PROCESSED_DIR / "holons.json").read_bytes()
    entity_extractor.extract()
    second = (C.PROCESSED_DIR / "holons.json").read_bytes()
    assert first == second, "extraction must be deterministic (seed=42)"


# --- dual model --------------------------------------------------------------
def test_dual_model_built():
    assert (C.RDF_HOLONIC_DIR / "model_a.trig").exists()
    assert (C.RDF_FLAT_DIR / "model_b.ttl").exists()
    stats = json.loads((C.RESULTS_DIR / "model_stats.json").read_text("utf-8"))
    assert stats["model_a"]["named_graphs"] > 200      # 4 layers/holon + registry
    assert stats["model_b"]["named_graphs"] == 0       # flat = single graph
    assert stats["reification_ratio"] >= 0.50, "≥50% of relations must be reified"


# --- benchmark: expressiveness + bijection -----------------------------------
def test_expressiveness_and_bijection():
    a, b = benchmark.load_models()
    bench = benchmark.run_benchmark(a, b)
    info = benchmark.check_information_preservation(a, b)
    summary = benchmark.summarise(bench, info)
    assert summary["total_queries"] == 50
    assert summary["expressiveness_gain"] >= 0.15, "H1: need >= 15% gain"
    assert summary["H1_supported"]
    assert not summary["result_mismatches"], "shared queries must agree across models"
    assert info["bijection_holds"], "A<->B information-preservation must hold"
    assert info["assertions_A"] == info["assertions_B"]


# --- graph topology + homomorphism -------------------------------------------
def test_graph_topology_and_homomorphism():
    m = graph_analysis.analyse()
    assert m["n_nodes"] >= 200
    cd = m["community_detection"]
    assert cd["modularity"] > 0.5, "holon graph should be strongly modular"
    assert cd["purity_vs_specialty"] >= 0.6, "communities should track specialties"
    assert all(v > 0 for v in m["homomorphism_patterns"].values()), "all 4 patterns match"
    assert len(m["subsumption_pairs"]) == 2, "need 2 worked subsumption pairs"


# --- Project 2 integration (SHACL) -------------------------------------------
def test_project2_shacl_integration():
    """A sample of hand-off holons (+entities) conforms to Project 2's flat shapes."""
    sys.path.insert(0, str(C.REPO_ROOT / "project_2_semantic" / "src"))
    try:
        from shacl_validator import validate_graph, load_ontology
        from rdflib import Graph
    except Exception:                                   # pragma: no cover
        pytest.skip("Project 2 validator/pyshacl not available")

    ent = Graph()
    for f in glob.glob(str(C.RDF_HOLONIC_DIR / "entities" / "*.ttl")):
        ent.parse(f, format="turtle")
    ent.parse(str(C.RDF_HOLONIC_DIR / "relationships.ttl"), format="turtle")
    ont = load_ontology()
    shapes_b = str(C.REPO_ROOT / "project_2_semantic/shacl/shapes/flat")

    files = sorted(glob.glob(str(C.RDF_HOLONIC_DIR / "clinical_questions" / "*.ttl")))[:5]
    assert files
    for f in files:
        g = Graph(); g.parse(f, format="turtle")
        for t in ent:
            g.add(t)
        conforms, _, violations = validate_graph(g, shapes_b, "sh:Violation", ont_graph=ont)
        assert conforms, f"{Path(f).name} should conform to Project 2 Set B: {violations[:2]}"
