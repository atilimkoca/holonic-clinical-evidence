"""
scoping_demo.py — empirical witness for Theorem 2 (§2.5 expressiveness proof).

Demonstrates that detectability of the cross-holon contradiction φ_T5 depends
on the VALIDATION SCOPE, exactly as the proof argues:

  Scenario 1 (Merged regime M):     both holon interiors in one graph
                                     -> interior cross-holon shape DETECTS.
  Scenario 2 (Scoped regime S):     validator sees only the focal holon's graph
                                     -> the SAME interior shape MISSES (the
                                        contradicting triple is out of scope) —
                                        a flat per-holon validator provably cannot
                                        decide φ_T5.
  Scenario 3 (Scoped + projection): the partner SURFACES its verdict into its
                                     projection layer, which scoped access DOES
                                     permit; a boundary/projection-aware shape
                                     reads the foreign projection -> DETECTS.

Scenario 3 is the mechanism that puts φ_T5 in C_S(L_bnd) ∖ C_S(L_flat):
boundary-aware SHACL carries a projection-surfacing obligation that flat SHACL
lacks. Run:

    ../../.venv/bin/python theory/scoping_demo.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from pyshacl import validate
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from shacl_validator import load_ontology  # noqa: E402

HOLON = Namespace("https://example.org/holon#")
OE = Namespace("https://example.org/openevidence#")
EX = Namespace("https://example.org/demo/")
REIFIES = URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#reifies")

drug, disease = EX.drugD, EX.diseaseE


def _assertion(g: Graph, ev: URIRef, holon: URIRef, eff: str) -> None:
    tt = URIRef(str(ev) + "-tt")
    g.add((drug, OE.treats, disease))
    g.add((tt, RDF.subject, drug)); g.add((tt, RDF.predicate, OE.treats))
    g.add((tt, RDF.object, disease))
    g.add((ev, RDF.type, HOLON.EvidenceAssertion))
    g.add((ev, REIFIES, tt))
    g.add((ev, HOLON.confidence, Literal("0.85", datatype=OE.decimal)))
    g.add((ev, OE.effectiveness, Literal(eff)))
    g.add((ev, HOLON.inHolon, holon))


def focal_graph() -> Graph:
    """Holon Hf: asserts the pair is 'effective' (interior)."""
    g = Graph()
    g.add((EX.Hf, RDF.type, HOLON.ClinicalQuestionHolon))
    _assertion(g, EX.evF, EX.Hf, "effective")
    return g


def partner_interior() -> Graph:
    """Holon Hp interior: asserts 'ineffective' for the same pair."""
    g = Graph()
    g.add((EX.Hp, RDF.type, HOLON.ClinicalQuestionHolon))
    _assertion(g, EX.evP, EX.Hp, "ineffective")
    return g


def partner_projection() -> Graph:
    """Holon Hp projection: surfaces the verdict so scoped peers can read it."""
    g = Graph()
    g.add((EX.Hp_prj, OE.projectsDrug, drug))
    g.add((EX.Hp_prj, OE.projectsDisease, disease))
    g.add((EX.Hp_prj, OE.effectiveness, Literal("ineffective")))
    return g


# --- Two shapes: an interior cross-holon shape and a projection-aware one -----

INTERIOR_T5 = """
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix holon: <https://example.org/holon#> .
@prefix oe: <https://example.org/openevidence#> .
oe:InteriorT5 a sh:NodeShape ; sh:targetClass holon:EvidenceAssertion ;
  sh:sparql [ sh:message "T5 via interiors" ; sh:severity sh:Violation ;
    sh:prefixes oe:_p ;
    sh:select \"\"\"
      SELECT $this WHERE {
        $this rdf:reifies ?t1 . ?t1 rdf:subject ?d ; rdf:predicate oe:treats ; rdf:object ?e .
        $this oe:effectiveness "effective" . $this holon:inHolon ?h1 .
        ?o rdf:reifies ?t2 . ?t2 rdf:subject ?d ; rdf:predicate oe:treats ; rdf:object ?e .
        ?o oe:effectiveness "ineffective" . ?o holon:inHolon ?h2 . FILTER(?h1 != ?h2)
      }\"\"\" ] .
oe:_p sh:declare [ sh:prefix "rdf" ; sh:namespace "http://www.w3.org/1999/02/22-rdf-syntax-ns#"^^<http://www.w3.org/2001/XMLSchema#anyURI> ] ,
                 [ sh:prefix "oe" ; sh:namespace "https://example.org/openevidence#"^^<http://www.w3.org/2001/XMLSchema#anyURI> ] ,
                 [ sh:prefix "holon" ; sh:namespace "https://example.org/holon#"^^<http://www.w3.org/2001/XMLSchema#anyURI> ] .
"""

PROJECTION_T5 = """
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix holon: <https://example.org/holon#> .
@prefix oe: <https://example.org/openevidence#> .
oe:ProjectionT5 a sh:NodeShape ; sh:targetClass holon:EvidenceAssertion ;
  sh:sparql [ sh:message "T5 via partner projection" ; sh:severity sh:Violation ;
    sh:prefixes oe:_p ;
    sh:select \"\"\"
      SELECT $this WHERE {
        $this rdf:reifies ?t1 . ?t1 rdf:subject ?d ; rdf:predicate oe:treats ; rdf:object ?e .
        $this oe:effectiveness "effective" .
        ?prj oe:projectsDrug ?d ; oe:projectsDisease ?e ; oe:effectiveness "ineffective" .
      }\"\"\" ] .
oe:_p sh:declare [ sh:prefix "rdf" ; sh:namespace "http://www.w3.org/1999/02/22-rdf-syntax-ns#"^^<http://www.w3.org/2001/XMLSchema#anyURI> ] ,
                 [ sh:prefix "oe" ; sh:namespace "https://example.org/openevidence#"^^<http://www.w3.org/2001/XMLSchema#anyURI> ] ,
                 [ sh:prefix "holon" ; sh:namespace "https://example.org/holon#"^^<http://www.w3.org/2001/XMLSchema#anyURI> ] .
"""


def _detected(data: Graph, shapes_ttl: str, ont: Graph) -> bool:
    conforms, _, _ = validate(
        data, shacl_graph=Graph().parse(data=shapes_ttl, format="turtle"),
        ont_graph=ont, inference="none", advanced=True)
    return not conforms


def main() -> None:
    ont = load_ontology()

    # Scenario 1 — merged: both interiors visible.
    merged = focal_graph() + partner_interior()
    s1 = _detected(merged, INTERIOR_T5, ont)

    # Scenario 2 — scoped: only the focal holon's graph is in scope.
    scoped = focal_graph()
    s2 = _detected(scoped, INTERIOR_T5, ont)

    # Scenario 3 — scoped + partner projection surfaced (no partner interior).
    scoped_proj = focal_graph() + partner_projection()
    s3 = _detected(scoped_proj, PROJECTION_T5, ont)

    print("Theorem 2 witness — cross-holon contradiction φ_T5")
    print("-" * 58)
    print(f"  S1 merged regime (interiors visible)          detected={s1}  (expect True)")
    print(f"  S2 scoped regime, interior shape, focal only  detected={s2}  (expect False)")
    print(f"  S3 scoped regime + partner PROJECTION surfaced detected={s3}  (expect True)")
    print("-" * 58)
    ok = (s1 is True and s2 is False and s3 is True)
    print("Interpretation: under scoped access a flat per-holon (interior-only)")
    print("validator CANNOT decide φ_T5 (S2). Boundary-aware SHACL adds the")
    print("projection-surfacing obligation (S3) that makes it decidable —")
    print("exactly C_S(L_bnd) \\ C_S(L_flat).  Witness consistent: " + str(ok))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
