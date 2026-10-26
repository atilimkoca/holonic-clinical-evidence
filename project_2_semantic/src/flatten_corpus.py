"""flatten_corpus.py — flat-RDF export of the inconsistency corpus (Set C).

Produces the data side of the reviewer-requested third condition:

    Set C = FLAT RDF + context-aware SPARQL SHACL.

The export mirrors the RQ1 flat baseline: every assertional fact survives
(drug/disease/source entities, reified evidence assertions with confidence,
level, dates, effectiveness, citations, and the holon-membership fact
holon:inHolon), while the holonic ORGANISATIONAL structure is removed:

  * layer-graph links   — holon:hasInteriorGraph / hasBoundaryGraph /
                          hasProjectionGraph / hasContextGraph
  * boundary events     — holon:EntityEntry / holon:EntityExit nodes and
                          every triple about them
  * boundary admission  — holon:evidenceQualityThreshold (a governance RULE,
                          not a data fact; Set C's shapes must fall back to
                          the schema-level default of 0.50)

Summary-level literals (holon:aggregateConfidence, holon:narrativeFunction,
holon:summaryConfidence) are data facts and are retained, exactly as the RQ1
flat baseline "preserves the same facts".

Reads  corpus/holons/*.ttl (+ manifest.csv)
Writes corpus/holons_flat/*.ttl (+ the same manifest.csv)

Run:
    python src/flatten_corpus.py
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from rdflib import Graph, Namespace
from rdflib.namespace import RDF

HOLON = Namespace("https://example.org/holon#")

_PROJ = Path(__file__).resolve().parents[1]

# Layer/boundary structure stripped by the flat export.
_LAYER_LINKS = (
    HOLON.hasInteriorGraph, HOLON.hasBoundaryGraph,
    HOLON.hasProjectionGraph, HOLON.hasContextGraph,
)
_BOUNDARY_EVENT_TYPES = (HOLON.EntityEntry, HOLON.EntityExit)
_BOUNDARY_RULES = (HOLON.evidenceQualityThreshold,)


def flatten_graph(g: Graph) -> Graph:
    """Return a copy of `g` without holonic organisational structure."""
    out = Graph()
    for prefix, ns in g.namespaces():
        out.bind(prefix, ns)

    boundary_nodes = set()
    for t in _BOUNDARY_EVENT_TYPES:
        boundary_nodes |= set(g.subjects(RDF.type, t))

    for s, p, o in g:
        if s in boundary_nodes or o in boundary_nodes:
            continue                       # boundary entry/exit events
        if p in _LAYER_LINKS:
            continue                       # layer-graph links
        if p in _BOUNDARY_RULES:
            continue                       # boundary admission metadata
        out.add((s, p, o))
    return out


def run(corpus_dir: Path, out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    for ttl in sorted(corpus_dir.glob("*.ttl")):
        g = Graph()
        g.parse(ttl, format="turtle")
        flat = flatten_graph(g)
        flat.serialize(out_dir / ttl.name, format="turtle")
        n += 1
    manifest = corpus_dir / "manifest.csv"
    if manifest.exists():
        shutil.copy(manifest, out_dir / "manifest.csv")
    return n


def main() -> None:
    ap = argparse.ArgumentParser(description="Flat-RDF export of the corpus (Set C data).")
    ap.add_argument("--corpus", default=str(_PROJ / "corpus" / "holons"))
    ap.add_argument("--out", default=str(_PROJ / "corpus" / "holons_flat"))
    args = ap.parse_args()
    n = run(Path(args.corpus), Path(args.out))
    print(f"Flattened {n} holon files -> {args.out}")


if __name__ == "__main__":
    main()
