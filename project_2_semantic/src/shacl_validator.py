"""
shacl_validator.py — pySHACL wrapper for the holonic semantic layer (Project 2).

Implements the Project 2 -> Project 3 API contract:

    conforms, report_ttl, violations = validate_graph(
        data_path, shapes_path, severity_threshold="sh:Warning")

`shapes_path` may be a single .ttl file or a directory of .ttl files (all are
merged). The shared + project ontologies are loaded as the ontology graph. RDFS
inference is deliberately disabled during validation; pySHACL still uses the
ontology graph for class checks such as SystematicReview -> EvidenceSource.
SPARQL constraints require advanced mode.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

from pyshacl import validate
from rdflib import Graph, Namespace
from rdflib.namespace import RDF

SH = Namespace("http://www.w3.org/ns/shacl#")

_THIS = Path(__file__).resolve()
_PROJ = _THIS.parents[1]                      # project_2_semantic/
_SHARED = _PROJ.parent / "shared"             # Final_Project/shared/

SEVERITY_RANK = {"sh:Info": 0, "sh:Warning": 1, "sh:Violation": 2}
_SEV_URI = {
    SH.Info: "sh:Info", SH.Warning: "sh:Warning", SH.Violation: "sh:Violation",
}


def load_ontology() -> Graph:
    """Merge shared + project ontologies into one graph for sh:class reasoning."""
    g = Graph()
    for ttl in (
        _SHARED / "ontology" / "holon_core.ttl",
        _SHARED / "ontology" / "openevidence_vocab.ttl",
        _PROJ / "ontology" / "holon_ontology.ttl",
    ):
        if ttl.exists():
            g.parse(ttl, format="turtle")
    return g


def load_shapes(shapes_path: Union[str, Path]) -> Graph:
    """Load a shapes file or every .ttl in a shapes directory."""
    p = Path(shapes_path)
    g = Graph()
    files = sorted(p.glob("**/*.ttl")) if p.is_dir() else [p]
    for f in files:
        g.parse(f, format="turtle")
    return g


def _extract_violations(report: Graph, severity_threshold: str) -> list[dict]:
    """Pull validation results at or above the severity threshold into dicts."""
    threshold = SEVERITY_RANK.get(severity_threshold, 1)
    out: list[dict] = []
    for res in report.subjects(RDF.type, SH.ValidationResult):
        sev_uri = report.value(res, SH.resultSeverity)
        sev = _SEV_URI.get(sev_uri, "sh:Violation")
        if SEVERITY_RANK[sev] < threshold:
            continue
        out.append({
            "severity": sev,
            "focus_node": str(report.value(res, SH.focusNode)),
            "path": str(report.value(res, SH.resultPath) or ""),
            "message": str(report.value(res, SH.resultMessage) or ""),
            "source_shape": str(report.value(res, SH.sourceShape) or ""),
            "value": str(report.value(res, SH.value) or ""),
        })
    return out


def validate_graph(
    data_path: Union[str, Path, Graph],
    shapes_path: Union[str, Path, Graph],
    severity_threshold: str = "sh:Warning",
    ont_graph: Optional[Graph] = None,
) -> tuple[bool, str, list[dict]]:
    """Validate a data graph against a SHACL shapes set.

    Returns (conforms, report_ttl, violations) where `conforms` is judged at
    the requested severity threshold (a graph with only sub-threshold results
    is reported as conforming for the caller's purposes).
    """
    data_graph = data_path if isinstance(data_path, Graph) else Graph().parse(
        str(data_path), format="turtle")
    shapes_graph = shapes_path if isinstance(shapes_path, Graph) else load_shapes(
        shapes_path)
    ontology = ont_graph if ont_graph is not None else load_ontology()

    _, report_graph, report_text = validate(
        data_graph,
        shacl_graph=shapes_graph,
        ont_graph=ontology,
        # inference disabled on purpose: rdfs:domain axioms would otherwise
        # cross-type holons (e.g. a holon carrying evidenceQualityThreshold
        # would be inferred an EvidenceChainHolon), producing false positives.
        # sh:class still honours rdfs:subClassOf from ont_graph without it.
        inference="none",
        advanced=True,
        meta_shacl=False,
        debug=False,
    )

    if not isinstance(report_graph, Graph):
        # pyshacl returns a ValidationFailure object on engine errors (e.g. a
        # malformed SPARQL constraint). Surface it loudly rather than silently
        # treating the holon as conforming.
        raise RuntimeError(f"pySHACL engine failure: {report_text}")

    violations = _extract_violations(report_graph, severity_threshold)
    conforms = len(violations) == 0
    return conforms, report_text, violations


def detect(
    data_path: Union[str, Path, Graph],
    shapes_graph: Graph,
    ont_graph: Graph,
    severity_threshold: str = "sh:Violation",
) -> tuple[bool, list[dict]]:
    """Fast path for the experiment loop: returns (flagged, violations).

    `flagged` is True iff at least one result at/above the threshold fired,
    i.e. the shape set judged this holon inconsistent.
    """
    conforms, _, violations = validate_graph(
        data_path, shapes_graph, severity_threshold, ont_graph=ont_graph)
    return (not conforms), violations


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Validate a Turtle file against a SHACL set.")
    ap.add_argument("data")
    ap.add_argument("shapes")
    ap.add_argument("--severity", default="sh:Violation")
    args = ap.parse_args()

    conforms, report_text, violations = validate_graph(
        args.data, args.shapes, args.severity)
    print(f"conforms={conforms}  violations={len(violations)}")
    for v in violations[:20]:
        print(f"  [{v['severity']}] {v['focus_node']} :: {v['message']}")
