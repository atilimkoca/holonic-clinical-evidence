"""
Behaviour tests for Project 3 (Student C, RQ3).

Run from the repo root or project_3_llm:
    ../.venv/bin/python -m pytest project_3_llm/tests -q
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_PROJ = Path(__file__).resolve().parents[1]
_REPO = _PROJ.parents[0]
sys.path.insert(0, str(_PROJ / "src"))
sys.path.insert(0, str(_REPO / "project_2_semantic" / "src"))

from shacl_to_prompt import (load_shapes, node_shapes, transform,        # noqa: E402
                             render_prompt, P2_SHAPES)
from llm_provider import get_provider, MockProvider                      # noqa: E402
from llm_generator import (generate, parse_turtle, grounding_from_facts, # noqa: E402
                           _retrieved_context_block, _serialization_contract)
from evaluation import (classify_fact, cohens_kappa, evaluate_generation,  # noqa: E402
                        corpus_index)
from dataset import load_testset, Question                               # noqa: E402
from graph_rag import DualRAG                                            # noqa: E402
from context_budget import items_from_questions, greedy_knapsack, dp_knapsack  # noqa: E402
from neo4j_query import natural_language_query                           # noqa: E402
from shacl_validator import load_ontology                               # noqa: E402
from namespaces import OED, OEDRUG, OESRC                               # noqa: E402


@pytest.fixture(scope="module")
def shapes_graph():
    return load_shapes(P2_SHAPES)


@pytest.fixture(scope="module")
def cq_template(shapes_graph):
    cq = next(s for s in node_shapes(shapes_graph)
              if str(s).endswith("ClinicalQuestionShape"))
    return transform(shapes_graph, cq)


@pytest.fixture(scope="module")
def engine(shapes_graph):
    from shacl_validator import load_shapes as p2_load
    return p2_load(P2_SHAPES), load_ontology()


# --- Transform (§3.1) ------------------------------------------------------- #

def test_transform_is_deterministic(shapes_graph):
    cq = next(s for s in node_shapes(shapes_graph)
              if str(s).endswith("ClinicalQuestionShape"))
    t1, t2 = transform(shapes_graph, cq), transform(shapes_graph, cq)
    assert t1.required_fields() == t2.required_fields()
    assert render_prompt(t1) == render_prompt(t2)


def test_transform_extracts_required_fields(shapes_graph):
    reifier = next(s for s in node_shapes(shapes_graph)
                   if str(s).endswith("EvidenceReifierShape"))
    req = transform(shapes_graph, reifier).required_fields()
    assert "holon:confidence" in req
    assert "oe:evidenceLevel" not in req       # evidenceLevel is holon: not oe:
    assert "holon:evidenceLevel" in req
    assert "oe:cites" in req


# --- Generation loop (§3.1) ------------------------------------------------- #

def _ctx():
    return {
        "holon_id": "t1", "holon_uri": "https://example.org/openevidence/questions/q_t1",
        "question": "First-line drug for hypertension?", "specialty": "Cardiology",
        "answer_text": "Lisinopril is first-line.",
        "facts": [{"s": str(OEDRUG.lisinopril), "o": str(OED.hypertension),
                   "source": str(OESRC["34567890"]), "confidence": 0.95,
                   "level": "Level-1A", "effectiveness": "effective"}],
        "noise_facts": [],
    }


def test_system_A_conforms_first_pass(cq_template, engine):
    shapes, ont = engine
    r = generate(cq_template, _ctx(), system="A", shapes_graph=shapes, ont_graph=ont)
    assert r.first_pass is True
    assert r.passed is True


def test_system_B_fails_first_then_converges(cq_template, engine):
    shapes, ont = engine
    r = generate(cq_template, _ctx(), system="B", shapes_graph=shapes, ont_graph=ont, k=3)
    assert r.first_pass is False        # naive misses the holon scaffold
    assert r.passed is True             # converges via SHACL repair


def test_generated_output_parses(cq_template, engine):
    shapes, ont = engine
    r = generate(cq_template, _ctx(), system="A", shapes_graph=shapes, ont_graph=ont)
    assert parse_turtle(r.output_ttl) is not None


def test_real_provider_context_respects_retrieval_strategy():
    ctx = _ctx()
    noise = {"s": "https://example.org/openevidence/drugs/noise",
             "o": "https://example.org/openevidence/diseases/noise",
             "source": "https://example.org/openevidence/sources/noise"}
    ctx["noise_facts"] = [noise]
    prompt_a = _retrieved_context_block(ctx, "A")
    prompt_b = _retrieved_context_block(ctx, "B")
    assert noise["s"] not in prompt_a
    assert noise["s"] in prompt_b
    assert ctx["facts"][0]["s"] in prompt_a and ctx["facts"][0]["s"] in prompt_b


# --- 2x2 ablation systems C/D (reviewer request) ----------------------------- #

def test_system_C_boundary_retrieval_naive_prompt(cq_template, engine):
    """C = boundary retrieval + naive prompt: conformance behaves like B
    (no SHACL scaffold on the first pass), context stays noise-free like A."""
    shapes, ont = engine
    r = generate(cq_template, _ctx(), system="C", shapes_graph=shapes,
                 ont_graph=ont, k=3)
    assert r.first_pass is False       # naive prompt misses the holon scaffold
    assert r.passed is True            # converges via SHACL repair


def test_system_D_naive_retrieval_shacl_prompt(cq_template, engine):
    """D = naive retrieval + SHACL prompt: conforms first-pass like A."""
    shapes, ont = engine
    r = generate(cq_template, _ctx(), system="D", shapes_graph=shapes,
                 ont_graph=ont, k=3)
    assert r.first_pass is True


def test_ablation_context_visibility_matches_retrieval_factor():
    ctx = _ctx()
    noise = {"s": "https://example.org/openevidence/drugs/noise",
             "o": "https://example.org/openevidence/diseases/noise",
             "source": "https://example.org/openevidence/sources/noise"}
    ctx["noise_facts"] = [noise]
    assert noise["s"] not in _retrieved_context_block(ctx, "C")   # boundary
    assert noise["s"] in _retrieved_context_block(ctx, "D")       # naive


def test_dualrag_routes_ablation_systems():
    rag = DualRAG()
    q = rag.questions[0]
    a, b = rag.context(q, "A"), rag.context(q, "B")
    c, d = rag.context(q, "C"), rag.context(q, "D")
    assert (c.system, d.system) == ("C", "D")
    assert c.noise_facts == [] and c.context_tokens == a.context_tokens
    assert d.noise_facts == b.noise_facts and d.context_tokens == b.context_tokens
    with pytest.raises(ValueError):
        rag.context(q, "E")


def test_shared_contract_targets_same_resource_and_separate_fact():
    contract = _serialization_contract(_ctx())
    assert "a holon:ClinicalQuestionHolon" in contract
    assert "separate top-level" in contract
    assert "never place a complete triple after a semicolon" in contract


# --- Hallucination classifier (§3.3) --------------------------------------- #

def test_classifier_grounded_and_typeB():
    q = load_testset()[0]
    drug, dis = q.facts[0]["s"], q.facts[0]["o"]
    grounded = {(drug, dis)}
    geff = {(drug, dis): q.facts[0].get("effectiveness")}
    assert classify_fact((drug, dis), "effective", grounded, geff) in ("grounded", "C")
    fab = ("https://example.org/openevidence/drugs/zzznotreal", dis)
    assert classify_fact(fab, None, grounded, geff) == "B"


def test_typeA_is_corpus_but_ungrounded():
    corpus_pairs, _ = corpus_index()
    # pick a corpus pair and a DIFFERENT question's grounded set
    pair = next(iter(corpus_pairs))
    other = {("https://example.org/openevidence/drugs/none",
              "https://example.org/openevidence/diseases/none")}
    assert classify_fact(pair, None, other, {}) == "A"


def test_cohens_kappa_bounds():
    assert cohens_kappa(["g", "a", "b"], ["g", "a", "b"]) == 1.0
    assert -1.0 <= cohens_kappa(["g", "a", "b", "g"], ["a", "g", "b", "g"]) <= 1.0


def test_systemA_zero_hallucination(cq_template, engine):
    shapes, ont = engine
    rag = DualRAG()
    q = rag.questions[0]
    rA = generate(cq_template, rag.context(q, "A").to_generator_context(),
                  system="A", shapes_graph=shapes, ont_graph=ont)
    rep = evaluate_generation(rA.output_ttl, q, "A")
    assert rep.hallucination_rate == 0.0


# --- Context budget (§3.4) -------------------------------------------------- #

def test_greedy_within_half_of_optimal():
    items = items_from_questions()
    for L in (100, 400, 800):
        _, gval = greedy_knapsack(items, L)
        opt = dp_knapsack(items, L)
        assert gval <= opt + 1e-6
        assert gval >= 0.5 * opt - 1e-6     # the 1/2-approximation guarantee


# --- Dataset (§3.2) --------------------------------------------------------- #

def test_testset_has_100_questions():
    qs = load_testset()
    assert len(qs) == 100
    assert all(q.facts for q in qs)


# --- NL query interface (API contract) ------------------------------------- #

def test_natural_language_query_offline():
    res = natural_language_query("What is the recommended treatment for epilepsy?")
    assert res.backend in ("rdflib", "neo4j")
    assert "SELECT" in res.sparql and "MATCH" in res.cypher
    assert isinstance(res.results, list)


# --- Provider (scaffold) ---------------------------------------------------- #

def test_mock_provider_deterministic():
    p = get_provider("mock")
    assert isinstance(p, MockProvider)
    spec = {"task": "answer", "facts": [{"s": "a/x", "o": "b/y", "confidence": 0.9}],
            "noise_facts": []}
    r1 = p.complete("q", mock_spec=spec, use_cache=False)
    r2 = p.complete("q", mock_spec=spec, use_cache=False)
    assert r1.text == r2.text
