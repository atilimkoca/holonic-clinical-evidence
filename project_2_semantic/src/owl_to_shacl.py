"""
owl_to_shacl.py — OWL -> SHACL conversion with a formal loss analysis (§2.6).

Reads an OWL ontology and emits (a) a SHACL shapes graph for the axioms that
have a faithful SHACL encoding and (b) a loss report listing the axioms that do
NOT, with the reason. This operationalises the completeness question of §2.6:

    Conversion completeness.  Let A(O) be the axioms of O and let conv ⊆ A(O)
    be those with a validation-equivalent SHACL shape (every model violating the
    axiom is flagged by the shape and vice-versa, under the closed-graph
    validation semantics). Completeness(O) = |conv| / |A(O)|. The residue
    A(O) \\ conv is the *conversion loss*.

The loss is not incidental: it is the gap between OWL's entailment semantics
(open-world, inference of new triples) and SHACL's validation semantics
(closed-graph, no inference). Axioms that ENTAIL new triples (inverseOf,
Transitive/Symmetric, sameAs, equivalentClass) have no validation analogue.

Run:
    ../../.venv/bin/python src/owl_to_shacl.py
"""
from __future__ import annotations

import argparse
from pathlib import Path

from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS, XSD
from rdflib.util import guess_format

SH = Namespace("http://www.w3.org/ns/shacl#")
GEN = Namespace("https://example.org/medical/shapes#")

_PROJ = Path(__file__).resolve().parents[1]


def _local(uri: URIRef) -> str:
    s = str(uri)
    return s.split("#")[-1].split("/")[-1]


class OwlToShacl:
    def __init__(self, owl_graph: Graph):
        self.o = owl_graph
        self.s = Graph()                      # output shapes
        self.s.bind("sh", SH)
        self.s.bind("gen", GEN)
        self.loss: list[dict] = []            # unconvertible axioms
        self.converted: list[str] = []        # human-readable log
        self._node_shapes: dict[URIRef, URIRef] = {}

    # -- node-shape registry ------------------------------------------------
    def _shape_for(self, cls: URIRef) -> URIRef:
        if cls not in self._node_shapes:
            ns = GEN[_local(cls) + "Shape"]
            self.s.add((ns, RDF.type, SH.NodeShape))
            self.s.add((ns, SH.targetClass, cls))
            self._node_shapes[cls] = ns
        return self._node_shapes[cls]

    def _prop_block(self, shape: URIRef, path: URIRef) -> BNode:
        b = BNode()
        self.s.add((shape, SH.property, b))
        self.s.add((b, SH.path, path))
        return b

    # -- conversion passes ---------------------------------------------------
    def convert(self) -> None:
        self._classes()
        self._disjoint()
        self._domain_range()
        self._functional()
        self._restrictions()
        self._lossy_axioms()

    def _classes(self) -> None:
        for c in self.o.subjects(RDF.type, OWL.Class):
            if isinstance(c, URIRef):
                self._shape_for(c)
        # named subclass is structural (handled by sh:class transitivity); log it
        for sub, sup in self.o.subject_objects(RDFS.subClassOf):
            if isinstance(sub, URIRef) and isinstance(sup, URIRef):
                self.converted.append(f"subClassOf({_local(sub)},{_local(sup)}) "
                                      f"-> structural (sh:class honours it)")

    def _disjoint(self) -> None:
        for a, b in self.o.subject_objects(OWL.disjointWith):
            if isinstance(a, URIRef) and isinstance(b, URIRef):
                shape = self._shape_for(a)
                notb = BNode()
                self.s.add((shape, SH.NOT if False else SH["not"], notb))
                self.s.add((notb, SH["class"], b))
                self.converted.append(
                    f"disjointWith({_local(a)},{_local(b)}) -> sh:not [sh:class {_local(b)}]")

    def _domain_range(self) -> None:
        for p in set(self.o.subjects(RDF.type, OWL.ObjectProperty)) | \
                 set(self.o.subjects(RDF.type, OWL.DatatypeProperty)):
            doms = list(self.o.objects(p, RDFS.domain))
            rngs = list(self.o.objects(p, RDFS.range))
            is_data = (p, RDF.type, OWL.DatatypeProperty) in self.o
            for dom in doms:
                if not isinstance(dom, URIRef):
                    continue
                b = self._prop_block(self._shape_for(dom), p)
                for r in rngs:
                    if is_data:
                        self.s.add((b, SH.datatype, r))
                        self.converted.append(
                            f"range({_local(p)},{_local(r)}) -> sh:datatype")
                    elif isinstance(r, URIRef):
                        self.s.add((b, SH["class"], r))
                        self.converted.append(
                            f"domain/range({_local(p)}) -> sh:property[sh:class {_local(r)}]")

    def _functional(self) -> None:
        for p in self.o.subjects(RDF.type, OWL.FunctionalProperty):
            for dom in self.o.objects(p, RDFS.domain):
                if not isinstance(dom, URIRef):
                    continue
                b = self._prop_block(self._shape_for(dom), p)
                self.s.add((b, SH.maxCount, Literal(1)))
                self.converted.append(f"FunctionalProperty({_local(p)}) -> sh:maxCount 1")

    def _restrictions(self) -> None:
        for c, r in self.o.subject_objects(RDFS.subClassOf):
            if (r, RDF.type, OWL.Restriction) not in self.o:
                continue
            prop = self.o.value(r, OWL.onProperty)
            if prop is None or not isinstance(c, URIRef):
                continue
            shape = self._shape_for(c)
            some = self.o.value(r, OWL.someValuesFrom)
            allv = self.o.value(r, OWL.allValuesFrom)
            card = self.o.value(r, OWL.cardinality)
            mincard = self.o.value(r, OWL.minCardinality)
            maxcard = self.o.value(r, OWL.maxCardinality)
            if some is not None:
                b = self._prop_block(shape, prop)
                qv = BNode()
                self.s.add((b, SH.qualifiedValueShape, qv))
                self.s.add((qv, SH["class"], some))
                self.s.add((b, SH.qualifiedMinCount, Literal(1)))
                self.converted.append(
                    f"someValuesFrom({_local(prop)},{_local(some)}) "
                    f"-> sh:qualifiedValueShape minCount 1")
            if allv is not None:
                b = self._prop_block(shape, prop)
                self.s.add((b, SH["class"], allv))
                self.converted.append(
                    f"allValuesFrom({_local(prop)},{_local(allv)}) -> sh:class (all values)")
            if card is not None:
                b = self._prop_block(shape, prop)
                self.s.add((b, SH.minCount, Literal(int(card))))
                self.s.add((b, SH.maxCount, Literal(int(card))))
                self.converted.append(
                    f"cardinality({_local(prop)})={int(card)} -> sh:minCount/maxCount")
            if mincard is not None:
                b = self._prop_block(shape, prop)
                self.s.add((b, SH.minCount, Literal(int(mincard))))
                self.converted.append(f"minCardinality({_local(prop)}) -> sh:minCount")
            if maxcard is not None:
                b = self._prop_block(shape, prop)
                self.s.add((b, SH.maxCount, Literal(int(maxcard))))
                self.converted.append(f"maxCardinality({_local(prop)}) -> sh:maxCount")

    # -- the lossy residue ---------------------------------------------------
    def _lossy_axioms(self) -> None:
        def add_loss(kind, detail, reason):
            self.loss.append({"axiom": kind, "detail": detail, "reason": reason})

        for a, b in self.o.subject_objects(OWL.equivalentClass):
            add_loss("equivalentClass", f"{_local(a)} ≡ {_local(b)}",
                     "SHACL has no class-equivalence axiom; cannot entail mutual membership.")
        for a, b in self.o.subject_objects(OWL.inverseOf):
            add_loss("inverseOf", f"{_local(a)} ⁻¹ {_local(b)}",
                     "SHACL validates existing triples but cannot ENTAIL the inverse edge.")
        for p in self.o.subjects(RDF.type, OWL.TransitiveProperty):
            add_loss("TransitiveProperty", _local(p),
                     "No transitive-closure entailment; paths validate reachability, not inference.")
        for p in self.o.subjects(RDF.type, OWL.SymmetricProperty):
            add_loss("SymmetricProperty", _local(p),
                     "Cannot entail the symmetric triple; only validate if already present.")
        for a, b in self.o.subject_objects(OWL.sameAs):
            add_loss("sameAs", f"{_local(a)} = {_local(b)}",
                     "SHACL has no identity reasoning / individual merging.")

    # -- completeness --------------------------------------------------------
    def completeness(self) -> tuple[int, int, float]:
        n_conv = len(self.converted)
        n_loss = len(self.loss)
        total = n_conv + n_loss
        return n_conv, n_loss, (n_conv / total if total else 1.0)


def run(owl_path: Path, out_shapes: Path, out_report: Path) -> None:
    fmt = guess_format(str(owl_path)) or "turtle"   # .rdf/.owl -> xml, .ttl -> turtle
    o = Graph().parse(owl_path, format=fmt)
    conv = OwlToShacl(o)
    conv.convert()
    out_shapes.write_text(conv.s.serialize(format="turtle"))

    n_conv, n_loss, comp = conv.completeness()
    lines = ["# §2.6 — OWL → SHACL Conversion Loss Report\n",
             f"Source: `{owl_path.name}`\n",
             f"- Convertible axioms: **{n_conv}**",
             f"- Lossy axioms: **{n_loss}**",
             f"- **Completeness = {comp:.0%}**\n",
             "\n## Converted (faithful SHACL encoding)\n"]
    for c in conv.converted:
        lines.append(f"- {c}")
    lines.append("\n## Lossy residue (no validation-equivalent SHACL)\n")
    lines.append("| OWL axiom | Detail | Why it cannot convert |")
    lines.append("|-----------|--------|------------------------|")
    for L in conv.loss:
        lines.append(f"| `{L['axiom']}` | {L['detail']} | {L['reason']} |")
    lines.append(
        "\n## Why the loss is structural\n"
        "Every lossy axiom is an **entailment** axiom: it licenses the inference "
        "of triples that are not asserted (an inverse edge, a transitive hop, an "
        "identity merge, a class equivalence). SHACL's semantics is **closed-graph "
        "validation** — it checks the triples present, it never derives new ones. "
        "The convertible axioms are exactly the **constraint** axioms (cardinality, "
        "domain/range typing, disjointness, existential/universal restrictions), "
        "which map to shape conditions. Hence the OWL→SHACL frontier coincides with "
        "the **entailment vs constraint** boundary, and completeness < 100% is "
        "*inherent*, not a tool limitation.\n")
    out_report.write_text("\n".join(lines))

    print(f"Converted {n_conv} axioms, {n_loss} lossy. Completeness={comp:.0%}")
    print(f"Shapes  -> {out_shapes}")
    print(f"Report  -> {out_report}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Convert an OWL ontology to SHACL with loss analysis.")
    ap.add_argument("--owl", default=str(_PROJ / "ontology" / "medical_subset.ttl"))
    ap.add_argument("--shapes", default=str(_PROJ / "shacl" / "shapes" / "generated_from_owl.ttl"))
    ap.add_argument("--report", default=str(_PROJ / "theory" / "owl_to_shacl_loss.md"))
    args = ap.parse_args()
    run(Path(args.owl), Path(args.shapes), Path(args.report))


if __name__ == "__main__":
    main()
