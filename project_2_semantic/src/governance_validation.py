"""
governance_validation.py — §2.7 governance-dependent validation experiment.

Measures how SHACL validation behaves under the three governance topologies of
the assignment (and feeds RQ₄ from the validation angle):

  C1 Centralized : one engine validates the UNION of all holon graphs.
                   -> global consistency: cross-holon contradictions ARE caught.
  C2 Federated   : each holon validated against its own graph + the PROJECTIONS
                   of its peers (shared boundary). -> cross-holon caught IFF the
                   peer surfaced its verdict into its projection layer.
  C3 Autonomous  : each holon self-validates on its own interior only.
                   -> cross-holon contradictions are INVISIBLE (out of scope).

We also record validation latency and scale N to expose the
centralized/distributed trade-off:
  - Centralized pays one big-graph validation (global consistency, single point
    of failure, costly schema evolution).
  - Autonomous pays N small validations (cheap, parallelisable, evolvable) but
    forfeits cross-holon detection.
  - Federated recovers cross-holon detection at the cost of projection plumbing.

This is the operational counterpart of Theorem 2 (§2.5): the governance topology
*is* the validation scope, and the scope decides what is detectable.

Run:
    ../../.venv/bin/python src/governance_validation.py
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

from pyshacl import validate
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF

from shacl_validator import load_ontology, load_shapes

HOLON = Namespace("https://example.org/holon#")
OE = Namespace("https://example.org/openevidence#")
EX = Namespace("https://example.org/gov/")
REIFIES = URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#reifies")

_PROJ = Path(__file__).resolve().parents[1]
SET_A = _PROJ / "shacl" / "shapes" / "boundary_aware"

# Two single-branch cross-holon shapes (pyshacl does not pre-bind $this through
# a SPARQL UNION, so we split the interior and projection variants). Each regime
# uses the one whose evidence its access model makes visible.
_PFX = """
oe:_gp sh:declare [ sh:prefix "rdf" ; sh:namespace "http://www.w3.org/1999/02/22-rdf-syntax-ns#"^^<http://www.w3.org/2001/XMLSchema#anyURI> ] ,
                  [ sh:prefix "oe" ; sh:namespace "https://example.org/openevidence#"^^<http://www.w3.org/2001/XMLSchema#anyURI> ] ,
                  [ sh:prefix "holon" ; sh:namespace "https://example.org/holon#"^^<http://www.w3.org/2001/XMLSchema#anyURI> ] .
"""

# Interior variant: fires when both contradicting INTERIORS are in scope (C1).
INTERIOR_SHAPE = """
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix holon: <https://example.org/holon#> .
@prefix oe: <https://example.org/openevidence#> .
oe:GovInterior a sh:NodeShape ; sh:targetClass holon:EvidenceAssertion ;
  sh:sparql [ sh:message "cross-holon contradiction (interiors)" ; sh:severity sh:Violation ;
    sh:prefixes oe:_gp ;
    sh:select \"\"\"
      SELECT $this WHERE {
        $this rdf:reifies ?t1 . ?t1 rdf:subject ?d ; rdf:predicate oe:treats ; rdf:object ?e .
        $this oe:effectiveness "effective" . $this holon:inHolon ?h1 .
        ?o rdf:reifies ?t2 . ?t2 rdf:subject ?d ; rdf:predicate oe:treats ; rdf:object ?e .
        ?o oe:effectiveness "ineffective" . ?o holon:inHolon ?h2 . FILTER(?h1 != ?h2)
      }\"\"\" ] .
""" + _PFX

# Projection variant: fires when a peer's PROJECTION surfaces the verdict (C2).
PROJECTION_SHAPE = """
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix holon: <https://example.org/holon#> .
@prefix oe: <https://example.org/openevidence#> .
oe:GovProjection a sh:NodeShape ; sh:targetClass holon:EvidenceAssertion ;
  sh:sparql [ sh:message "cross-holon contradiction (peer projection)" ; sh:severity sh:Violation ;
    sh:prefixes oe:_gp ;
    sh:select \"\"\"
      SELECT $this WHERE {
        $this rdf:reifies ?t1 . ?t1 rdf:subject ?d ; rdf:predicate oe:treats ; rdf:object ?e .
        $this oe:effectiveness "effective" .
        ?prj oe:projectsDrug ?d ; oe:projectsDisease ?e ; oe:effectiveness "ineffective" .
      }\"\"\" ] .
""" + _PFX


def _assertion(g: Graph, ev: URIRef, holon: URIRef, d: URIRef, e: URIRef, eff: str):
    tt = URIRef(str(ev) + "-tt")
    g.add((d, OE.treats, e))
    g.add((tt, RDF.subject, d)); g.add((tt, RDF.predicate, OE.treats)); g.add((tt, RDF.object, e))
    g.add((ev, RDF.type, HOLON.EvidenceAssertion)); g.add((ev, REIFIES, tt))
    g.add((ev, OE.effectiveness, Literal(eff)))
    g.add((ev, HOLON.inHolon, holon))


def build_system(n: int, n_contradictions: int):
    """Return per-holon (interior, projection) graphs for N holons, with
    `n_contradictions` cross-holon contradicting pairs."""
    holons = []
    for i in range(n):
        interior, projection = Graph(), Graph()
        h = EX[f"h{i}"]
        interior.add((h, RDF.type, HOLON.ClinicalQuestionHolon))
        d, e = EX[f"drug{i}"], EX[f"disease{i}"]
        _assertion(interior, EX[f"ev{i}"], h, d, e, "effective")
        # projection surfaces this holon's verdict (boundary obligation)
        projection.add((EX[f"prj{i}"], OE.projectsDrug, d))
        projection.add((EX[f"prj{i}"], OE.projectsDisease, e))
        projection.add((EX[f"prj{i}"], OE.effectiveness, Literal("effective")))
        holons.append({"id": h, "drug": d, "disease": e,
                       "interior": interior, "projection": projection,
                       "contradicts": False})
    # Inject contradictions: holon j asserts 'ineffective' for holon 0..k's pair.
    for k in range(min(n_contradictions, n - 1)):
        src = holons[k]
        partner = holons[n - 1 - k]
        _assertion(partner["interior"], EX[f"contra{k}"], partner["id"],
                   src["drug"], src["disease"], "ineffective")
        # partner surfaces the contradicting verdict into its projection
        pj = partner["projection"]
        node = EX[f"contraprj{k}"]
        pj.add((node, OE.projectsDrug, src["drug"]))
        pj.add((node, OE.projectsDisease, src["disease"]))
        pj.add((node, OE.effectiveness, Literal("ineffective")))
        src["contradicts"] = True               # src holon is now part of a contradiction
    return holons


SH = Namespace("http://www.w3.org/ns/shacl#")


def _flagged_nodes(data: Graph, shapes: Graph, ont: Graph) -> set:
    """Return the set of focus nodes that triggered a violation."""
    _, report, _ = validate(data, shacl_graph=shapes, ont_graph=ont,
                            inference="none", advanced=True)
    if not isinstance(report, Graph):
        return set()
    return set(report.objects(None, SH.focusNode))


def run_regime(regime: str, holons, interior_shape: Graph,
               projection_shape: Graph, ont: Graph):
    """Return (detected_count, gold_count, latency_seconds).

    A contradicted holon counts as 'detected' iff its own 'effective' assertion
    (ev{i}) is flagged under that regime's access model. Every regime validates
    all N holons, so latency never depends on knowing the gold labels.
    """
    gold = sum(1 for h in holons if h["contradicts"])
    detected, t0 = 0, time.perf_counter()

    if regime == "C1":                            # centralized: union of interiors
        union = Graph()
        for h in holons:
            union += h["interior"]
        flagged = _flagged_nodes(union, interior_shape, ont)
        detected = sum(1 for h in holons if h["contradicts"]
                       and EX[f"ev{_idx(h)}"] in flagged)

    elif regime == "C3":                          # autonomous: own interior only
        for h in holons:
            flagged = _flagged_nodes(h["interior"], interior_shape, ont)
            if h["contradicts"] and EX[f"ev{_idx(h)}"] in flagged:
                detected += 1                     # stays 0: partner out of scope

    elif regime == "C2":                          # federated: interior + peer projections
        all_proj = Graph()
        for h in holons:
            all_proj += h["projection"]
        for h in holons:
            view = Graph()
            view += h["interior"]
            view += all_proj                      # shared boundary projections
            flagged = _flagged_nodes(view, projection_shape, ont)
            if h["contradicts"] and EX[f"ev{_idx(h)}"] in flagged:
                detected += 1

    return detected, gold, time.perf_counter() - t0


def _idx(h) -> int:
    """Recover a holon's index from its URI (…/hN)."""
    return int(str(h["id"]).rsplit("h", 1)[-1])


def run(sizes, results_dir: Path, c1_max: int = 500):
    results_dir.mkdir(parents=True, exist_ok=True)
    ont = load_ontology()
    interior_shape = Graph().parse(data=INTERIOR_SHAPE, format="turtle")
    projection_shape = Graph().parse(data=PROJECTION_SHAPE, format="turtle")

    rows = []
    for n in sizes:
        holons = build_system(n, n_contradictions=max(2, n // 10))
        for regime in ("C1", "C2", "C3"):
            # Centralized cross-holon validation is O(N^2) over one union graph;
            # above c1_max it is impractical — we record that explicitly rather
            # than waiting (this IS the scalability finding for C1).
            if regime == "C1" and n > c1_max:
                rows.append((regime, n, "n/a", "n/a", "n/a", "impractical(O(N^2))"))
                continue
            det, gold, lat = run_regime(regime, holons, interior_shape,
                                        projection_shape, ont)
            rate = det / gold if gold else 0.0
            rows.append((regime, n, det, gold, f"{rate:.2f}", f"{lat:.3f}"))

    import csv
    with (results_dir / "governance.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["regime", "n_holons", "detected", "gold", "detection_rate", "latency_s"])
        w.writerows(rows)

    label = {"C1": "Centralized", "C2": "Federated", "C3": "Autonomous"}
    print(f"{'regime':12} {'N':>4} {'detected/gold':>14} {'rate':>6} {'latency_s':>10}")
    for regime, n, det, gold, rate, lat in rows:
        print(f"{label[regime]:12} {n:>4} {f'{det}/{gold}':>14} {rate:>6} {lat:>10}")
    print(f"\nWritten to {results_dir / 'governance.csv'}")


def main() -> None:
    ap = argparse.ArgumentParser(description="§2.7 governance validation experiment.")
    ap.add_argument("--sizes", default="20,40,80")
    ap.add_argument("--results", default=str(_PROJ / "results"))
    ap.add_argument("--c1-max", type=int, default=500,
                    help="skip centralized (O(N^2)) above this size")
    args = ap.parse_args()
    sizes = [int(x) for x in args.sizes.split(",")]
    run(sizes, Path(args.results), c1_max=args.c1_max)


if __name__ == "__main__":
    main()
