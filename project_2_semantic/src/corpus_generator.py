"""
corpus_generator.py — Inconsistency corpus for RQ2 (Project 2, Student B).

Builds a controlled gold-standard corpus of holons, half fully consistent and
half carrying exactly one deliberately injected defect drawn from the T1–T6
taxonomy:

    T1  Structural   — missing / malformed required field
    T2  Referential  — points at an undeclared (untyped) entity
    T3  Temporal      — chronological impossibility
    T4  Semantic      — SHACL-valid field-by-field but inadmissible in context
    T5  Cross-holon   — two holons assert contradictory verdicts
    T6  Projection    — projected summary diverges from interior evidence

RDF 1.2 reification is MATERIALISED: each annotated triple becomes a reifier
node typed holon:EvidenceAssertion, linked by rdf:reifies to a triple-term
node carrying rdf:subject / rdf:predicate / rdf:object, plus the annotation
properties. This keeps the corpus parseable by rdflib 7.x (which does not yet
read the Turtle-1.2 `{| |}` syntax). See README "Threats to Validity".

Deterministic: a fixed RNG seed makes the corpus fully reproducible.
"""
from __future__ import annotations

import argparse
import csv
import random
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Callable, Optional

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, XSD

# RDF 1.2 term not present in rdflib's closed RDF namespace; declare explicitly.
RDF_REIFIES = URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#reifies")

HOLON = Namespace("https://example.org/holon#")
OE = Namespace("https://example.org/openevidence#")
OEQ = Namespace("https://example.org/openevidence/questions/")
OED = Namespace("https://example.org/openevidence/diseases/")
OEDRUG = Namespace("https://example.org/openevidence/drugs/")
OESRC = Namespace("https://example.org/openevidence/sources/")
OEEVT = Namespace("https://example.org/openevidence/events/")
PROV = Namespace("http://www.w3.org/ns/prov#")

SPECIALTIES = ["Cardiology", "Neurology", "Oncology", "Pulmonology",
               "Endocrinology", "Nephrology", "Psychiatry"]
LEVELS = ["Level-1A", "Level-1B", "Level-2A", "Level-2B", "Level-3"]

# Inconsistency type codes; "C" = consistent (no defect).
TYPES = ["T1", "T2", "T3", "T4", "T5", "T6"]


# Per-type annotation: (severity, layer, location-path) — written to the
# manifest so every inconsistency is tagged with type + location + severity
# (assignment §2.3: "Her tutarsızlık tipi, lokasyonu, ve ciddiyeti etiketlenmeli").
TYPE_META = {
    "C":  ("none",      "-",          "-"),
    "T1": ("Violation", "interior",   "ev{i}_0 / holon:confidence"),
    "T2": ("Violation", "interior",   "ev{i}_0 / oe:cites -> ghost{i}"),
    "T3": ("Violation", "interior",   "ev{i}_0 / holon:recordedOn"),
    "T4": ("Violation", "boundary",   "ev{i}_0 / holon:confidence vs holon:evidenceQualityThreshold"),
    "T5": ("Violation", "cross-holon","ev{i}_partner / oe:effectiveness"),
    "T6": ("Violation", "projection", "chain{i} / holon:aggregateConfidence vs interior mean"),
}


@dataclass
class CorpusItem:
    holon_id: str
    gold_label: str        # "C" or "T1".."T6"
    defect_desc: str
    graph: Graph
    severity: str = "none"
    layer: str = "-"
    location: str = "-"


def _bind(g: Graph) -> None:
    g.bind("holon", HOLON)
    g.bind("oe", OE)
    g.bind("oeq", OEQ)
    g.bind("oed", OED)
    g.bind("oedrug", OEDRUG)
    g.bind("oesrc", OESRC)
    g.bind("oeevt", OEEVT)
    g.bind("prov", PROV)


def _entities(g: Graph, i: int):
    """Declare a self-contained drug / disease / symptom / source set."""
    drug = OEDRUG[f"drug{i}"]
    disease = OED[f"disease{i}"]
    symptom = OE[f"symptom{i}"]
    source = OESRC[f"src{i}"]

    g.add((drug, RDF.type, OE.Drug))
    g.add((drug, RDFS.label, Literal(f"Drug-{i}", lang="en")))
    g.add((drug, OE.atcCode, Literal("C09AA03", datatype=XSD.string)))
    g.add((drug, OE.approvalDate, Literal("2010-01-01", datatype=XSD.date)))

    g.add((disease, RDF.type, OE.Disease))
    g.add((disease, RDFS.label, Literal(f"Disease-{i}", lang="en")))
    g.add((disease, OE.icdCode, Literal("I10", datatype=XSD.string)))
    g.add((disease, OE.firstDescribedDate, Literal("1990-01-01", datatype=XSD.date)))

    g.add((symptom, RDF.type, OE.Symptom))
    g.add((symptom, RDFS.label, Literal(f"Symptom-{i}", lang="en")))

    g.add((source, RDF.type, OE.SystematicReview))
    g.add((source, RDFS.label, Literal(f"Source-{i}", lang="en")))
    g.add((source, OE.pubmedId, Literal(str(30000000 + i), datatype=XSD.string)))
    g.add((source, OE.publicationDate, Literal("2018-01-01", datatype=XSD.date)))
    return drug, disease, symptom, source


def _add_layers(g: Graph, holon: URIRef) -> None:
    g.add((holon, HOLON.hasInteriorGraph, URIRef(str(holon) + "-int")))
    g.add((holon, HOLON.hasBoundaryGraph, URIRef(str(holon) + "-bnd")))
    g.add((holon, HOLON.hasProjectionGraph, URIRef(str(holon) + "-prj")))
    g.add((holon, HOLON.hasContextGraph, URIRef(str(holon) + "-ctx")))


def _add_assertion(g: Graph, ev: URIRef, holon: URIRef, drug: URIRef,
                   disease: URIRef, source: URIRef, conf: float, level: str,
                   recorded: str, effectiveness: Optional[str] = None) -> None:
    """Materialise one RDF 1.2 reified `drug oe:treats disease` assertion."""
    g.add((drug, OE.treats, disease))                       # base (asserted) triple
    tt = URIRef(str(ev) + "-tt")                            # triple-term node
    g.add((tt, RDF.subject, drug))
    g.add((tt, RDF.predicate, OE.treats))
    g.add((tt, RDF.object, disease))

    g.add((ev, RDF.type, HOLON.EvidenceAssertion))
    g.add((ev, RDF_REIFIES, tt))
    g.add((ev, HOLON.confidence, Literal(f"{conf:.2f}", datatype=XSD.decimal)))
    g.add((ev, HOLON.evidenceLevel, Literal(level)))
    g.add((ev, HOLON.assessedBy, OEQ.openevidence_ai))
    g.add((ev, HOLON.recordedOn, Literal(recorded, datatype=XSD.date)))
    g.add((ev, OE.cites, source))
    g.add((ev, HOLON.inHolon, holon))
    if effectiveness is not None:
        g.add((ev, OE.effectiveness, Literal(effectiveness)))


def build_consistent(i: int, as_chain: bool = False) -> Graph:
    """A fully valid holon that both Set A and Set B should pass."""
    g = Graph()
    _bind(g)
    rng = random.Random(i)
    drug, disease, symptom, source = _entities(g, i)

    if as_chain:
        holon = OEQ[f"chain{i}"]
        g.add((holon, RDF.type, HOLON.EvidenceChainHolon))
        g.add((holon, HOLON.evidenceQualityThreshold,
               Literal("0.50", datatype=XSD.decimal)))
    else:
        holon = OEQ[f"q{i}"]
        g.add((holon, RDF.type, HOLON.ClinicalQuestionHolon))
        g.add((holon, OE.questionText,
               Literal(f"What is the first-line treatment for Disease-{i}?",
                       datatype=XSD.string)))
        g.add((holon, OE.answerText,
               Literal(f"Drug-{i} is recommended as first-line therapy.",
                       datatype=XSD.string)))
        g.add((holon, OE.belongsToSpecialty, Literal(rng.choice(SPECIALTIES))))
        g.add((holon, HOLON.evidenceQualityThreshold,
               Literal("0.50", datatype=XSD.decimal)))

    _add_layers(g, holon)
    g.add((holon, RDFS.label, Literal(f"Holon {i}", lang="en")))

    # Two interior assertions with coherent confidences.
    confs = [round(rng.uniform(0.7, 0.95), 2), round(rng.uniform(0.7, 0.95), 2)]
    for k, conf in enumerate(confs):
        ev = OEEVT[f"ev{i}_{k}"]
        _add_assertion(g, ev, holon, drug, disease, source, conf,
                       rng.choice(["Level-1A", "Level-1B"]), "2020-06-01",
                       effectiveness="effective")

    if as_chain:
        # Projection aggregate is coherent with the interior mean.
        mean = sum(confs) / len(confs)
        g.add((holon, HOLON.aggregateConfidence,
               Literal(f"{mean:.2f}", datatype=XSD.decimal)))

    # Boundary entry event (valid).
    entry = OEEVT[f"entry{i}"]
    g.add((entry, RDF.type, HOLON.EntityEntry))
    g.add((entry, HOLON.entity, disease))
    g.add((entry, HOLON.entryMode, Literal("topic-match")))

    # Projection narrative.
    g.add((holon, HOLON.narrativeFunction,
           Literal(f"Establishes Drug-{i} as first-line for Disease-{i}", lang="en")))
    g.add((holon, HOLON.summaryConfidence, Literal("0.85", datatype=XSD.decimal)))
    return g


# --------------------------------------------------------------------------- #
# Defect injectors. Each takes the index and returns (graph, description).
# --------------------------------------------------------------------------- #

def inject_T1(i: int):
    """Structural: remove the mandatory confidence from an assertion."""
    g = build_consistent(i)
    ev = OEEVT[f"ev{i}_0"]
    for o in list(g.objects(ev, HOLON.confidence)):
        g.remove((ev, HOLON.confidence, o))
    return g, "Removed mandatory holon:confidence from ev0 (missing required field)."


def inject_T2(i: int):
    """Referential: cite a source that is never typed as an EvidenceSource."""
    g = build_consistent(i)
    ev = OEEVT[f"ev{i}_0"]
    for o in list(g.objects(ev, OE.cites)):
        g.remove((ev, OE.cites, o))
    dangling = OESRC[f"ghost{i}"]            # referenced but never declared
    g.add((ev, OE.cites, dangling))
    return g, "Citation points to an undeclared (untyped) source node."


def inject_T3(i: int):
    """Temporal: record the evidence before the cited source was published."""
    g = build_consistent(i)
    ev = OEEVT[f"ev{i}_0"]
    for o in list(g.objects(ev, HOLON.recordedOn)):
        g.remove((ev, HOLON.recordedOn, o))
    g.add((ev, HOLON.recordedOn, Literal("2015-01-01", datatype=XSD.date)))  # < src 2018
    return g, "Evidence recordedOn (2015) precedes cited source publication (2018)."


def inject_T4(i: int):
    """Semantic: 'effective' verdict whose confidence is below the holon's
    evidence-quality threshold — valid field-by-field, inadmissible in context."""
    g = build_consistent(i)
    ev = OEEVT[f"ev{i}_0"]
    for o in list(g.objects(ev, HOLON.confidence)):
        g.remove((ev, HOLON.confidence, o))
    g.add((ev, HOLON.confidence, Literal("0.30", datatype=XSD.decimal)))   # < 0.50 thr
    # effectiveness already "effective" from build_consistent
    return g, "'effective' claim at confidence 0.30 below holon threshold 0.50 (T4)."


def inject_T5(i: int):
    """Cross-holon: a second holon in the same file asserts the OPPOSITE
    effectiveness for the same drug-disease pair."""
    g = build_consistent(i)
    drug, disease = OEDRUG[f"drug{i}"], OED[f"disease{i}"]
    src = OESRC[f"src{i}"]
    partner = OEQ[f"q{i}_partner"]
    g.add((partner, RDF.type, HOLON.ClinicalQuestionHolon))
    g.add((partner, OE.questionText,
           Literal(f"Is Drug-{i} effective for Disease-{i}?", datatype=XSD.string)))
    g.add((partner, OE.answerText, Literal("Evidence suggests no benefit.",
                                           datatype=XSD.string)))
    g.add((partner, OE.belongsToSpecialty, Literal("Cardiology")))
    g.add((partner, HOLON.evidenceQualityThreshold, Literal("0.50", datatype=XSD.decimal)))
    _add_layers(g, partner)
    g.add((partner, HOLON.narrativeFunction, Literal("Contradicts the first holon", lang="en")))
    g.add((partner, HOLON.summaryConfidence, Literal("0.80", datatype=XSD.decimal)))
    evp = OEEVT[f"ev{i}_partner"]
    _add_assertion(g, evp, partner, drug, disease, src, 0.82, "Level-1A",
                   "2021-01-01", effectiveness="ineffective")
    return g, "Partner holon asserts 'ineffective' for the same drug-disease (T5)."


def inject_T6(i: int):
    """Projection: aggregate confidence diverges from the interior mean by >0.25."""
    g = build_consistent(i, as_chain=True)
    for o in list(g.objects(OEQ[f"chain{i}"], HOLON.aggregateConfidence)):
        g.remove((OEQ[f"chain{i}"], HOLON.aggregateConfidence, o))
    g.add((OEQ[f"chain{i}"], HOLON.aggregateConfidence,
           Literal("0.20", datatype=XSD.decimal)))   # interior mean ~0.8 -> diff>0.25
    return g, "Projection aggregateConfidence 0.20 vs interior mean ~0.8 (T6)."


INJECTORS: dict[str, Callable[[int], tuple]] = {
    "T1": inject_T1, "T2": inject_T2, "T3": inject_T3,
    "T4": inject_T4, "T5": inject_T5, "T6": inject_T6,
}


def generate(n_consistent: int = 50, n_per_type: Optional[dict] = None,
             seed: int = 42) -> list[CorpusItem]:
    """Generate the corpus. Defaults to 50 consistent + 50 inconsistent
    (roughly balanced across T1–T6)."""
    rng = random.Random(seed)
    items: list[CorpusItem] = []

    # Consistent holons (mix of question + chain holons).
    for k in range(n_consistent):
        idx = 1000 + k
        as_chain = (k % 3 == 0)
        g = build_consistent(idx, as_chain=as_chain)
        sev, layer, loc = TYPE_META["C"]
        items.append(CorpusItem(f"C_{idx}", "C", "Fully consistent holon.", g,
                                sev, layer, loc))

    # Inconsistent holons, balanced across the six types.
    if n_per_type is None:
        base = {t: 8 for t in TYPES}          # 8*6 = 48 ~ 50
        base["T1"] += 1
        base["T2"] += 1                       # -> 50
        n_per_type = base
    idx = 2000
    for t, count in n_per_type.items():
        for _ in range(count):
            g, desc = INJECTORS[t](idx)
            sev, layer, loc = TYPE_META[t]
            items.append(CorpusItem(f"{t}_{idx}", t, desc, g, sev, layer,
                                    loc.format(i=idx)))
            idx += 1

    rng.shuffle(items)
    return items


def write_corpus(out_dir: Path, items: list[CorpusItem]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = out_dir / "manifest.csv"
    with manifest.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["holon_id", "gold_label", "file", "severity", "layer",
                    "defect_location", "defect_desc"])
        for it in items:
            fname = f"{it.holon_id}.ttl"
            (out_dir / fname).write_text(it.graph.serialize(format="turtle"))
            w.writerow([it.holon_id, it.gold_label, fname, it.severity,
                        it.layer, it.location, it.defect_desc])
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate the T1-T6 inconsistency corpus.")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "corpus" / "holons"))
    ap.add_argument("--consistent", type=int, default=50)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    items = generate(n_consistent=args.consistent, seed=args.seed)
    manifest = write_corpus(Path(args.out), items)
    n_incon = sum(1 for it in items if it.gold_label != "C")
    print(f"Wrote {len(items)} holons "
          f"({args.consistent} consistent, {n_incon} inconsistent) to {args.out}")
    print(f"Manifest: {manifest}")


if __name__ == "__main__":
    main()
