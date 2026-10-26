"""End-to-end integration smoke pipeline.

The assignment asks for a Crawl -> RDF -> Holon -> SHACL Validation -> LLM Query
-> Answer path. The full research experiments live in the three sub-projects;
this module proves that their public interfaces compose in one executable path.
It intentionally uses the cached Project 1 corpus, Project 2's boundary-aware
SHACL set, and Project 3's offline deterministic provider so it can run during
grading without secrets or services.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from rdflib import Graph, URIRef
from rdflib.namespace import RDF

REPO = Path(__file__).resolve().parents[2]
P1_HOLONS = REPO / "project_1_crawling" / "data" / "rdf" / "holonic" / "clinical_questions"
P1_ENTITIES = REPO / "project_1_crawling" / "data" / "rdf" / "holonic" / "entities"
P2_SRC = REPO / "project_2_semantic" / "src"
P2_SHAPES_A = REPO / "project_2_semantic" / "shacl" / "shapes" / "boundary_aware"
P3_SRC = REPO / "project_3_llm" / "src"
SHARED_TEST_SET = REPO / "shared" / "test_data" / "integration_test_set.ttl"
DEMO_DIR = REPO / "integration" / "demo"
DEMO_RESULT = DEMO_DIR / "end_to_end_result.json"

for p in (P2_SRC, P3_SRC):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from shacl_validator import load_ontology, load_shapes, validate_graph  # noqa: E402
from neo4j_query import natural_language_query                          # noqa: E402
from dataset import grounding_graph_for                                  # noqa: E402
from evaluation import evaluate_generation                               # noqa: E402
from graph_rag import DualRAG                                            # noqa: E402
from llm_generator import generate                                       # noqa: E402
from shacl_to_prompt import (                                            # noqa: E402
    load_shapes as load_shape_templates,
    node_shapes,
    transform,
)

HOLON_CLASS = "https://example.org/holon#ClinicalQuestionHolon"


def selected_holon_files(sample_size: int = 20) -> list[Path]:
    files = sorted(P1_HOLONS.glob("*.ttl"))
    if len(files) < sample_size:
        raise FileNotFoundError(f"Need {sample_size} holon TTL files under {P1_HOLONS}")
    return files[:sample_size]


def build_shared_integration_test_set(sample_size: int = 20) -> Path:
    """Materialise the 20-holon shared test set expected by the assignment."""
    g = Graph()
    for path in sorted(P1_ENTITIES.glob("*.ttl")):
        g.parse(path, format="turtle")
    for path in selected_holon_files(sample_size):
        g.parse(path, format="turtle")
    SHARED_TEST_SET.parent.mkdir(parents=True, exist_ok=True)
    g.serialize(destination=SHARED_TEST_SET, format="turtle")
    return SHARED_TEST_SET


def validate_holons(sample_size: int = 20) -> dict[str, Any]:
    shapes = load_shapes(P2_SHAPES_A)
    ontology = load_ontology()
    rows = []
    entity_graph = Graph()
    for entity_path in sorted(P1_ENTITIES.glob("*.ttl")):
        entity_graph.parse(entity_path, format="turtle")
    for path in selected_holon_files(sample_size):
        graph = Graph()
        for triple in entity_graph:
            graph.add(triple)
        graph.parse(path, format="turtle")
        conforms, _report, violations = validate_graph(
            graph, shapes, severity_threshold="sh:Violation", ont_graph=ontology
        )
        rows.append({
            "file": str(path.relative_to(REPO)),
            "conforms": conforms,
            "violations": len(violations),
        })
    return {
        "sample_size": sample_size,
        "conforming_holons": sum(1 for row in rows if row["conforms"]),
        "rows": rows,
    }


def run_generation_smoke() -> dict[str, Any]:
    rag = DualRAG()
    question = rag.questions[0]
    shapes_graph = load_shape_templates(P2_SHAPES_A)
    clinical_shape = next(
        shape for shape in node_shapes(shapes_graph)
        if str(shape).endswith("ClinicalQuestionShape")
    )
    template = transform(shapes_graph, clinical_shape)
    context = rag.context(question, "A")
    result = generate(
        template,
        context.to_generator_context(),
        system="A",
        grounding=grounding_graph_for(question),
        shapes_graph=load_shapes(P2_SHAPES_A),
        ont_graph=load_ontology(),
        write=False,
    )
    hallucination = evaluate_generation(result.output_ttl, question, "A")
    return {
        "holon_id": question.holon_id,
        "question": question.question,
        "first_pass_conforms": result.first_pass,
        "converged": result.passed,
        "iterations": result.iterations,
        "hallucination_rate": hallucination.hallucination_rate,
        "context_tokens": context.context_tokens,
    }


def run_pipeline(sample_size: int = 20) -> dict[str, Any]:
    shared_set_size = max(sample_size, 20)
    test_set_path = build_shared_integration_test_set(shared_set_size)
    validation = validate_holons(sample_size)
    query = natural_language_query(
        "What is the recommended treatment for epilepsy?",
        max_hops=3,
        include_confidence=True,
    )
    generation = run_generation_smoke()
    graph = Graph().parse(test_set_path, format="turtle")
    holon_count = len(list(graph.subjects(RDF.type, URIRef(HOLON_CLASS))))
    result = {
        "shared_test_set": str(test_set_path.relative_to(REPO)),
        "shared_test_set_triples": len(graph),
        "shared_test_set_holons": holon_count,
        "shared_test_set_requested_holons": shared_set_size,
        "validation": validation,
        "query": {
            "backend": query.backend,
            "result_count": len(query.results),
            "top_results": query.results[:5],
        },
        "generation": generation,
    }
    DEMO_DIR.mkdir(parents=True, exist_ok=True)
    DEMO_RESULT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the end-to-end integration smoke pipeline.")
    parser.add_argument("--sample-size", type=int, default=20)
    args = parser.parse_args()
    result = run_pipeline(args.sample_size)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
