"""rdf_transformer.py — build the dual RDF model from the normalised data.

Produces two information-equivalent encodings of the same clinical evidence
(assignment §1.2):

  Model A — Holonic (RDF 1.2 style).  An rdflib *Dataset* with one named graph
            per holon layer (interior / boundary / projection / context) plus a
            registry graph. Edge metadata is attached with the *materialised*
            RDF 1.2 reification pattern used by Project 2:
                <reifier> a holon:EvidenceAssertion ; rdf:reifies <tt> ; ...
                <tt> rdf:subject/predicate/object ...
            so the two sub-projects share one data convention. The conceptual
            target is Turtle 1.2 annotation syntax
            (:s :p :o ~ :r {| ... |}); we materialise it because rdflib/pyshacl
            cannot yet parse that surface syntax (documented threat to validity).

  Model B — Flat (RDF 1.1, baseline).  A single rdflib *Graph* (no named graphs)
            using *standard* RDF 1.1 reification (rdf:Statement +
            rdf:subject/predicate/object). The four-layer partition is not
            materialised as named graphs; it is recoverable via the documented
            predicate->layer map (see theory/information_preservation.md), so the
            two models are information-equivalent (a bijection exists) while
            differing in queryability — which is exactly what the expressiveness
            benchmark measures.

Outputs (under data/rdf/):
  holonic/model_a.trig                 full Model A dataset (named graphs)
  holonic/all_holonic.ttl              Model A merged into one graph (convenience)
  holonic/clinical_questions/*.ttl     Project 1 -> Project 2 hand-off (per holon)
  holonic/entities/{diseases,drugs,sources,symptoms,specialties}.ttl
  holonic/relationships.ttl            cross-entity relations (Project 2 contract)
  flat/model_b.ttl                     full Model B baseline
"""
from __future__ import annotations

import argparse
import json
from typing import Any, Optional

from rdflib import Dataset, Graph, Literal, URIRef
from rdflib.namespace import OWL, PROV, RDF, RDFS, XSD

from . import config as C
from . import namespaces as NS
from .namespaces import (HOLON, OE, OEAUTH, OED, OEDRUG, OEEVT, OEQ, OESPEC,
                         OESRC, OESYM)

AI_AGENT = OEQ["openevidence_ai"]

# rdflib's RDF namespace is closed and predates RDF 1.2, so `rdf:reifies` is not
# an attribute; reference it by full IRI (Project 2 uses the same predicate).
RDF_REIFIES = URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#reifies")

# Display names for oe:belongsToSpecialty. Project 2's ClinicalQuestionShape
# constrains this property with an sh:in list using spaced display names, so the
# multi-word specialty must be emitted as "Infectious Disease", not the config key.
SPECIALTY_DISPLAY = {"InfectiousDisease": "Infectious Disease"}


def spec_label(name: str) -> str:
    return SPECIALTY_DISPLAY.get(name, name)

# Predicate -> holon layer map (λ). Anchors the information-preservation proof:
# in Model B the layer partition is reconstructed from this function.
LAYER_OF_PREDICATE: dict[str, str] = {
    str(OE.questionText): "interior", str(OE.answerText): "interior",
    str(OE.treats): "interior", str(OE.causesSideEffect): "interior",
    str(RDF_REIFIES): "interior", str(OE.effectiveness): "interior",
    str(HOLON.inHolon): "interior", str(OE.cites): "interior",
    str(HOLON.evidenceQualityThreshold): "boundary",
    str(HOLON.narrativeFunction): "projection",
    str(HOLON.summaryConfidence): "projection",
    str(HOLON.aggregateConfidence): "projection",
    str(HOLON.prerequisiteFor): "projection",
    str(PROV.wasAttributedTo): "context", str(PROV.generatedAtTime): "context",
    str(PROV.wasDerivedFrom): "context", str(HOLON.recordedOn): "context",
}


def _load_processed() -> tuple[dict, list, dict]:
    P = C.PROCESSED_DIR
    entities = json.loads((P / "entities.json").read_text("utf-8"))
    holons = json.loads((P / "holons.json").read_text("utf-8"))
    hierarchy = json.loads((P / "hierarchy.json").read_text("utf-8"))
    return entities, holons, hierarchy


def _dec(x: float) -> Literal:
    return Literal(str(x), datatype=XSD.decimal)


def _date(x: str) -> Literal:
    return Literal(x, datatype=XSD.date)


# ----------------------------------------------------------------------------
# Entity triples (shared by both models, emitted into the target graph)
# ----------------------------------------------------------------------------
def _emit_entities(g: Graph, entities: dict) -> None:
    src_class = {
        "ClinicalTrial": OE.ClinicalTrial, "SystematicReview": OE.SystematicReview,
        "MetaAnalysis": OE.MetaAnalysis, "CaseReport": OE.CaseReport,
        "EvidenceSource": OE.EvidenceSource,
    }
    for slug, d in entities["diseases"].items():
        u = OED[slug]
        g.add((u, RDF.type, OE.Disease))
        g.add((u, RDFS.label, Literal(d["label"], lang="en")))
        g.add((u, OE.icdCode, Literal(d["icd10"], datatype=XSD.string)))
        g.add((u, OE.firstDescribedDate, _date(d["first_described_date"])))
        g.add((u, OE.inSpecialty, OESPEC[d["specialty"]]))
    for name, d in entities["drugs"].items():
        u = OEDRUG[name]
        g.add((u, RDF.type, OE.Drug))
        g.add((u, RDFS.label, Literal(d["label"], lang="en")))
        g.add((u, OE.atcCode, Literal(d["atc"], datatype=XSD.string)))
        g.add((u, OE.drugClass, Literal(d["drug_class"], datatype=XSD.string)))
        g.add((u, OE.approvalDate, _date(d["approval_date"])))
    for slug, d in entities["symptoms"].items():
        u = OESYM[slug]
        g.add((u, RDF.type, OE.Symptom))
        g.add((u, RDFS.label, Literal(d["label"], lang="en")))
    for name, d in entities["specialties"].items():
        u = OESPEC[name]
        g.add((u, RDF.type, OE.Specialty))
        g.add((u, RDFS.label, Literal(spec_label(name), lang="en")))
        g.add((u, RDFS.comment, Literal(d["description"], lang="en")))
    for pmid, s in entities["sources"].items():
        u = OESRC[pmid]
        g.add((u, RDF.type, src_class.get(s["source_class"], OE.EvidenceSource)))
        g.add((u, RDFS.label, Literal(s["title"] or f"Source {pmid}", lang="en")))
        g.add((u, OE.pubmedId, Literal(pmid, datatype=XSD.string)))
        g.add((u, OE.publicationDate, _date(s["publication_date"])))
        g.add((u, OE.evidenceLevelLabel, Literal(s["evidence_level"], datatype=XSD.string)))
        if s["journal"]:
            g.add((u, OE.journal, Literal(s["journal"], datatype=XSD.string)))


def _emit_cross_relations(g: Graph, entities: dict) -> int:
    """hasSymptom + contraindicatedWith + supersedes (non-reified, both models)."""
    n = 0
    for slug, d in entities["diseases"].items():
        for sym in d.get("symptoms", []):
            g.add((OED[slug], OE.hasSymptom, OESYM[sym])); n += 1
        drugs = d.get("drugs", [])
        # one contraindication pair per disease that has >=2 drugs of different class
        if len(drugs) >= 2:
            a, b = drugs[0], drugs[1]
            if entities["drugs"][a]["drug_class"] != entities["drugs"][b]["drug_class"]:
                g.add((OEDRUG[a], OE.contraindicatedWith, OEDRUG[b])); n += 1
    return n


# ----------------------------------------------------------------------------
# MODEL A — holonic dataset
# ----------------------------------------------------------------------------
def build_holonic(entities: dict, holons: list, hierarchy: dict) -> Dataset:
    ds = Dataset(default_union=True)
    NS.bind_all(ds)
    reg = ds.graph(OE.registry)          # holon nodes, hierarchy, entities, x-relations

    _emit_entities(reg, entities)
    n_cross = _emit_cross_relations(reg, entities)
    reg.add((AI_AGENT, RDF.type, PROV.Agent))
    reg.add((AI_AGENT, RDFS.label, Literal("OpenEvidence AI System", lang="en")))

    # --- hierarchy: Specialty -> Disease -> ClinicalQuestion (Difficulty A) ---
    for spec, sdata in hierarchy.items():
        spec_holon = OEQ[sdata["holon_id"]]
        reg.add((spec_holon, RDF.type, HOLON.Holon))
        reg.add((spec_holon, RDFS.label, Literal(f"{spec} domain holon", lang="en")))
        reg.add((spec_holon, OE.belongsToSpecialty, Literal(spec_label(spec))))
        reg.add((spec_holon, OE.coversSpecialty, OESPEC[spec]))
        for dslug, ddata in sdata["diseases"].items():
            dis_holon = OEQ[ddata["holon_id"]]
            reg.add((dis_holon, RDF.type, HOLON.DiseaseHolon))
            reg.add((dis_holon, RDFS.label, Literal(f"{entities['diseases'][dslug]['label']} holon", lang="en")))
            reg.add((dis_holon, OE.aboutDisease, OED[dslug]))
            reg.add((dis_holon, OE.belongsToSpecialty, Literal(spec_label(spec))))
            reg.add((spec_holon, HOLON.containsHolon, dis_holon))
            for qid in ddata["questions"]:
                reg.add((dis_holon, HOLON.containsHolon, OEQ[qid]))

    n_reified = 0
    by_id = {h["id"]: h for h in holons}
    # prerequisiteFor chains the 3 facets of each disease (projection-layer edges)
    facet_order = {"treatment": 0, "efficacy": 1, "safety": 2}

    for h in holons:
        hid = h["id"]
        node = OEQ[hid]
        g_int = ds.graph(OEQ[f"{hid}-int"])
        g_bnd = ds.graph(OEQ[f"{hid}-bnd"])
        g_prj = ds.graph(OEQ[f"{hid}-prj"])
        g_ctx = ds.graph(OEQ[f"{hid}-ctx"])

        # holon node + layer pointers (registry / default)
        reg.add((node, RDF.type, HOLON.ClinicalQuestionHolon))
        reg.add((node, RDFS.label, Literal(h["question_text"][:90], lang="en")))
        reg.add((node, HOLON.hasInteriorGraph, OEQ[f"{hid}-int"]))
        reg.add((node, HOLON.hasBoundaryGraph, OEQ[f"{hid}-bnd"]))
        reg.add((node, HOLON.hasProjectionGraph, OEQ[f"{hid}-prj"]))
        reg.add((node, HOLON.hasContextGraph, OEQ[f"{hid}-ctx"]))
        reg.add((node, OE.belongsToSpecialty, Literal(spec_label(h["specialty"]))))
        reg.add((node, OE.aboutDisease, OED[h["disease"]]))

        # interior layer
        g_int.add((node, OE.questionText, Literal(h["question_text"], datatype=XSD.string)))
        g_int.add((node, OE.answerText, Literal(h["answer_text"], datatype=XSD.string)))
        for pmid in h["citations"]:
            g_int.add((node, OE.cites, OESRC[pmid]))

        # reified evidence assertion (materialised RDF 1.2)
        if h["relation"] and h["drug"]:
            subj = OEDRUG[h["drug"]]
            pred = OE.treats if h["relation"] == "treats" else OE.causesSideEffect
            obj = OED[h["object"]] if h["object_kind"] == "disease" else OESYM[h["object"]]
            reifier = OEEVT[f"ev_{hid}"]
            tt = OEEVT[f"ev_{hid}-tt"]
            g_int.add((subj, pred, obj))                       # base triple
            g_int.add((reifier, RDF.type, HOLON.EvidenceAssertion))
            g_int.add((reifier, RDF_REIFIES, tt))
            g_int.add((tt, RDF.subject, subj))
            g_int.add((tt, RDF.predicate, pred))
            g_int.add((tt, RDF.object, obj))
            g_int.add((reifier, HOLON.confidence, _dec(h["confidence"])))
            # evidenceLevel/effectiveness as plain literals to match Project 2 sh:in lists
            g_int.add((reifier, HOLON.evidenceLevel, Literal(h["evidence_level"])))
            g_int.add((reifier, HOLON.assessedBy, AI_AGENT))
            g_int.add((reifier, HOLON.recordedOn, _date(h["recorded_on"])))
            g_int.add((reifier, HOLON.inHolon, node))
            g_int.add((reifier, OE.cites, OESRC[h["primary_pmid"]]))
            if h["relation"] == "treats":
                g_int.add((reifier, OE.effectiveness, Literal(h["effectiveness"])))
            n_reified += 1

        # boundary layer
        entry = OEEVT[f"entry_{hid}"]
        g_bnd.add((entry, RDF.type, HOLON.EntityEntry))
        g_bnd.add((entry, HOLON.entity, OED[h["disease"]]))
        g_bnd.add((entry, HOLON.entryMode, Literal("topic-match")))
        g_bnd.add((node, HOLON.evidenceQualityThreshold, _dec(h["evidence_quality_threshold"])))

        # projection layer
        g_prj.add((node, HOLON.narrativeFunction, Literal(h["narrative"], datatype=XSD.string)))
        g_prj.add((node, HOLON.summaryConfidence, _dec(h["summary_confidence"])))
        g_prj.add((node, HOLON.aggregateConfidence, _dec(h["aggregate_confidence"])))

        # context layer
        g_ctx.add((node, PROV.wasAttributedTo, AI_AGENT))
        g_ctx.add((node, PROV.generatedAtTime,
                   Literal(f"{h['recorded_on']}T10:00:00Z", datatype=XSD.dateTime)))
        g_ctx.add((node, PROV.wasDerivedFrom, URIRef("https://pubmed.ncbi.nlm.nih.gov/")))
        g_ctx.add((node, HOLON.recordedOn, _date(h["recorded_on"])))

    # prerequisiteFor edges between facet holons of the same disease
    for spec, sdata in hierarchy.items():
        for dslug, ddata in sdata["diseases"].items():
            qs = sorted(ddata["questions"], key=lambda q: facet_order.get(by_id[q]["facet"], 9))
            for a, b in zip(qs, qs[1:]):
                ds.graph(OEQ[f"{a}-prj"]).add((OEQ[a], HOLON.prerequisiteFor, OEQ[b]))

    return ds, {"reified": n_reified, "cross_relations": n_cross}


# ----------------------------------------------------------------------------
# MODEL B — flat baseline graph
# ----------------------------------------------------------------------------
def build_flat(entities: dict, holons: list, hierarchy: dict) -> tuple[Graph, dict]:
    g = Graph()
    NS.bind_all(g)
    _emit_entities(g, entities)
    n_cross = _emit_cross_relations(g, entities)
    g.add((AI_AGENT, RDF.type, PROV.Agent))
    g.add((AI_AGENT, RDFS.label, Literal("OpenEvidence AI System", lang="en")))

    for spec, sdata in hierarchy.items():
        spec_holon = OEQ[sdata["holon_id"]]
        g.add((spec_holon, RDF.type, HOLON.Holon))
        g.add((spec_holon, RDFS.label, Literal(f"{spec} domain holon", lang="en")))
        g.add((spec_holon, OE.belongsToSpecialty, Literal(spec_label(spec))))
        g.add((spec_holon, OE.coversSpecialty, OESPEC[spec]))
        for dslug, ddata in sdata["diseases"].items():
            dis_holon = OEQ[ddata["holon_id"]]
            g.add((dis_holon, RDF.type, HOLON.DiseaseHolon))
            g.add((dis_holon, RDFS.label, Literal(f"{entities['diseases'][dslug]['label']} holon", lang="en")))
            g.add((dis_holon, OE.aboutDisease, OED[dslug]))
            g.add((dis_holon, OE.belongsToSpecialty, Literal(spec_label(spec))))
            g.add((spec_holon, HOLON.containsHolon, dis_holon))
            for qid in ddata["questions"]:
                g.add((dis_holon, HOLON.containsHolon, OEQ[qid]))

    n_reified = 0
    for h in holons:
        node = OEQ[h["id"]]
        # NB: no named graphs; layer is recoverable via LAYER_OF_PREDICATE (λ)
        g.add((node, RDF.type, HOLON.ClinicalQuestionHolon))
        g.add((node, RDFS.label, Literal(h["question_text"][:90], lang="en")))
        g.add((node, OE.questionText, Literal(h["question_text"], datatype=XSD.string)))
        g.add((node, OE.answerText, Literal(h["answer_text"], datatype=XSD.string)))
        g.add((node, OE.belongsToSpecialty, Literal(spec_label(h["specialty"]))))
        g.add((node, OE.aboutDisease, OED[h["disease"]]))
        g.add((node, HOLON.evidenceQualityThreshold, _dec(h["evidence_quality_threshold"])))
        g.add((node, HOLON.narrativeFunction, Literal(h["narrative"], datatype=XSD.string)))
        g.add((node, HOLON.summaryConfidence, _dec(h["summary_confidence"])))
        g.add((node, HOLON.aggregateConfidence, _dec(h["aggregate_confidence"])))
        # context-layer provenance (kept so Model B is information-equivalent to A)
        g.add((node, PROV.wasAttributedTo, AI_AGENT))
        g.add((node, PROV.generatedAtTime,
               Literal(f"{h['recorded_on']}T10:00:00Z", datatype=XSD.dateTime)))
        g.add((node, PROV.wasDerivedFrom, URIRef("https://pubmed.ncbi.nlm.nih.gov/")))
        g.add((node, HOLON.recordedOn, _date(h["recorded_on"])))
        for pmid in h["citations"]:
            g.add((node, OE.cites, OESRC[pmid]))
        # boundary-layer entry event (flattened into the single graph)
        entry = OEEVT[f"entry_{h['id']}"]
        g.add((entry, RDF.type, HOLON.EntityEntry))
        g.add((entry, HOLON.entity, OED[h["disease"]]))
        g.add((entry, HOLON.entryMode, Literal("topic-match")))

        if h["relation"] and h["drug"]:
            subj = OEDRUG[h["drug"]]
            pred = OE.treats if h["relation"] == "treats" else OE.causesSideEffect
            obj = OED[h["object"]] if h["object_kind"] == "disease" else OESYM[h["object"]]
            # same IRI as Model A's reifier: both name the same assertion, so
            # cross-model result sets that select the assertion node are comparable.
            st = OEEVT[f"ev_{h['id']}"]
            g.add((subj, pred, obj))                          # base triple
            # STANDARD RDF 1.1 reification (rdf:Statement)
            g.add((st, RDF.type, RDF.Statement))
            g.add((st, RDF.subject, subj))
            g.add((st, RDF.predicate, pred))
            g.add((st, RDF.object, obj))
            g.add((st, HOLON.confidence, _dec(h["confidence"])))
            g.add((st, HOLON.evidenceLevel, Literal(h["evidence_level"])))
            g.add((st, HOLON.assessedBy, AI_AGENT))
            g.add((st, HOLON.recordedOn, _date(h["recorded_on"])))
            g.add((st, HOLON.inHolon, node))
            g.add((st, OE.cites, OESRC[h["primary_pmid"]]))
            if h["relation"] == "treats":
                g.add((st, OE.effectiveness, Literal(h["effectiveness"])))
            n_reified += 1

    # prerequisiteFor edges between facet holons of the same disease (match Model A)
    by_id = {h["id"]: h for h in holons}
    facet_order = {"treatment": 0, "efficacy": 1, "safety": 2}
    for spec, sdata in hierarchy.items():
        for dslug, ddata in sdata["diseases"].items():
            qs = sorted(ddata["questions"], key=lambda q: facet_order.get(by_id[q]["facet"], 9))
            for a, b in zip(qs, qs[1:]):
                g.add((OEQ[a], HOLON.prerequisiteFor, OEQ[b]))

    return g, {"reified": n_reified, "cross_relations": n_cross}


# ----------------------------------------------------------------------------
# Project 1 -> Project 2 hand-off (turtle, single graph, materialised)
# ----------------------------------------------------------------------------
def export_handoff(ds: Dataset, entities: dict, holons: list) -> None:
    """Per-holon turtle files + entity files matching shared/interfaces/api_contracts.md.

    Each holon file merges that holon's 4 layer graphs into one turtle graph so
    Project 2's pyshacl validator (which parses turtle into a single Graph) can
    consume it unchanged.
    """
    cq_dir = C.RDF_HOLONIC_DIR / "clinical_questions"
    ent_dir = C.RDF_HOLONIC_DIR / "entities"
    for h in holons:
        hid = h["id"]
        merged = Graph()
        NS.bind_all(merged)
        node = OEQ[hid]
        for layer in ("int", "bnd", "prj", "ctx"):
            for t in ds.graph(OEQ[f"{hid}-{layer}"]):
                merged.add(t)
        # carry the holon-node declaration + layer pointers
        for t in ds.graph(OE.registry).triples((node, None, None)):
            merged.add(t)
        merged.serialize(cq_dir / f"{hid}.ttl", format="turtle")

    # entity files — split by type into separate files (api_contracts layout)
    full = Graph(); NS.bind_all(full); _emit_entities(full, entities)
    splits = {
        "diseases.ttl": OE.Disease, "drugs.ttl": OE.Drug, "symptoms.ttl": OE.Symptom,
    }
    for fname, cls in splits.items():
        sub = Graph(); NS.bind_all(sub)
        for s in full.subjects(RDF.type, cls):
            for t in full.triples((s, None, None)):
                sub.add(t)
        sub.serialize(ent_dir / fname, format="turtle")
    # sources (multiple subclasses)
    src = Graph(); NS.bind_all(src)
    for cls in (OE.EvidenceSource, OE.ClinicalTrial, OE.SystematicReview, OE.MetaAnalysis, OE.CaseReport):
        for s in full.subjects(RDF.type, cls):
            for t in full.triples((s, None, None)):
                src.add(t)
    src.serialize(ent_dir / "sources.ttl", format="turtle")

    # relationships.ttl (cross-entity, per api_contracts)
    rel = Graph(); NS.bind_all(rel); _emit_cross_relations(rel, entities)
    rel.serialize(C.RDF_HOLONIC_DIR / "relationships.ttl", format="turtle")


def transform() -> dict[str, Any]:
    entities, holons, hierarchy = _load_processed()
    C.ensure_dirs()

    ds, a_stats = build_holonic(entities, holons, hierarchy)
    flat, b_stats = build_flat(entities, holons, hierarchy)

    # serialise Model A
    ds.serialize(C.RDF_HOLONIC_DIR / "model_a.trig", format="trig")
    merged = Graph(); NS.bind_all(merged)
    for s, p, o, _ in ds.quads((None, None, None, None)):   # Dataset iterates quads
        merged.add((s, p, o))
    merged.serialize(C.RDF_HOLONIC_DIR / "all_holonic.ttl", format="turtle")

    # serialise Model B
    flat.serialize(C.RDF_FLAT_DIR / "model_b.ttl", format="turtle")

    export_handoff(ds, entities, holons)

    n_named_graphs = sum(1 for _ in ds.graphs())
    stats = {
        "model_a": {
            "triples": len(merged),
            "named_graphs": n_named_graphs,
            "reified_assertions": a_stats["reified"],
            "cross_relations": a_stats["cross_relations"],
        },
        "model_b": {
            "triples": len(flat),
            "named_graphs": 0,
            "reified_assertions": b_stats["reified"],
            "cross_relations": b_stats["cross_relations"],
        },
    }
    # reification ratio over base relational triples (treats/causesSideEffect/hasSymptom/contraindicatedWith)
    base_rel = a_stats["reified"] + a_stats["cross_relations"]
    stats["reification_ratio"] = round(a_stats["reified"] / base_rel, 3) if base_rel else 0.0
    (C.RESULTS_DIR / "model_stats.json").write_text(json.dumps(stats, indent=2), "utf-8")

    print("RDF transform complete:")
    print(f"  Model A (holonic): {stats['model_a']['triples']} triples, "
          f"{stats['model_a']['named_graphs']} named graphs, "
          f"{stats['model_a']['reified_assertions']} reified assertions")
    print(f"  Model B (flat):    {stats['model_b']['triples']} triples, "
          f"{stats['model_b']['reified_assertions']} reified assertions")
    print(f"  Reification ratio (of base relations): {stats['reification_ratio']}")
    return stats


def main() -> None:
    argparse.ArgumentParser(description="Build Model A (holonic) + Model B (flat).").parse_args()
    transform()


if __name__ == "__main__":
    main()
