"""evaluation.py — hallucination / coverage / conformance metrics (§3.3, §3.7).

Parses an LLM-generated RDF graph, extracts its asserted `oe:treats` facts, and
grounds each against (i) the question's gold facts and (ii) the whole Project-1
corpus, classifying every ungrounded assertion by the §3.3 taxonomy:

    Type A — ungrounded but factual : pair absent from THIS question yet asserted
             by SOME corpus holon (the source exists, just not for this question).
    Type B — ungrounded & incorrect : pair absent from the whole corpus
             (fabricated drug/disease link).
    Type C — contradictory         : pair present in question/corpus but the
             emitted effectiveness contradicts the grounded verdict.

Metrics: hallucination_rate = (A+B+C)/n_assertions, information coverage,
precision@k. Also provides `cohens_kappa` for inter-annotator agreement.
Formal definitions: theory/hallucination_taxonomy.md.
"""
from __future__ import annotations

import sys
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Optional

from rdflib import Graph, URIRef
from rdflib.namespace import RDF

_SRC = Path(__file__).resolve().parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from namespaces import HOLON, OE, RDF_REIFIES                 # noqa: E402
from dataset import Question, corpus_facts_by_disease, load_corpus  # noqa: E402


@dataclass
class HallucinationReport:
    holon_id: str
    system: str
    n_assertions: int = 0
    grounded: int = 0
    type_a: int = 0
    type_b: int = 0
    type_c: int = 0
    coverage: float = 0.0
    precision_at_1: float = 0.0
    precision_at_3: float = 0.0
    details: list = field(default_factory=list)

    @property
    def n_hallucinations(self) -> int:
        return self.type_a + self.type_b + self.type_c

    @property
    def hallucination_rate(self) -> float:
        return self.n_hallucinations / self.n_assertions if self.n_assertions else 0.0


# --------------------------------------------------------------------------- #
# Corpus knowledge index (for Type A vs B and contradiction checks)
# --------------------------------------------------------------------------- #

@lru_cache(maxsize=1)
def corpus_index() -> tuple:
    """(corpus_pairs:set[(drug,disease)], corpus_eff:dict[pair]->Counter)."""
    by_dis = corpus_facts_by_disease(load_corpus())
    pairs = set()
    eff: dict = {}
    for facts in by_dis.values():
        for f in facts:
            key = (f.s, f.o)
            pairs.add(key)
            if f.effectiveness:
                eff.setdefault(key, Counter())[f.effectiveness] += 1
    return pairs, eff


def _opposite(e: str) -> str:
    return {"effective": "ineffective", "ineffective": "effective"}.get(e, "")


# --------------------------------------------------------------------------- #
# Extract asserted facts from a generated graph
# --------------------------------------------------------------------------- #

def extract_asserted(graph: Graph) -> list:
    """Asserted (drug, disease, effectiveness|None) facts, ordered so that
    fully-reified assertions precede bare `oe:treats` triples (the order an LLM
    emits grounded content before naive over-generation)."""
    eff: dict = {}
    structured = []
    for ev in graph.subjects(RDF.type, HOLON.EvidenceAssertion):
        tt = graph.value(ev, RDF_REIFIES)
        if tt is None:
            continue
        s, o = graph.value(tt, RDF.subject), graph.value(tt, RDF.object)
        if s is None or o is None:
            continue
        e = graph.value(ev, OE.effectiveness)
        key = (str(s), str(o))
        eff[key] = str(e) if e is not None else None
        structured.append(key)
    all_treats = {(str(s), str(o)) for s, o in graph.subject_objects(OE.treats)}
    bare = sorted(all_treats - set(structured))
    ordered = sorted(set(structured)) + bare
    return [(s, o, eff.get((s, o))) for (s, o) in ordered]


# --------------------------------------------------------------------------- #
# Classification + metrics
# --------------------------------------------------------------------------- #

def classify_fact(pair: tuple, emitted_eff: Optional[str],
                  grounded_pairs: set, grounded_eff: dict) -> str:
    """Return one of: grounded | A | B | C."""
    corpus_pairs, corpus_eff = corpus_index()
    if pair in grounded_pairs:
        gold = grounded_eff.get(pair)
        if emitted_eff and gold and emitted_eff != gold:
            return "C"                              # contradicts this question
        return "grounded"
    if pair in corpus_pairs:
        # ungrounded for this question; contradiction vs corpus consensus -> C
        cons = corpus_eff.get(pair)
        if emitted_eff and cons and emitted_eff == _opposite(cons.most_common(1)[0][0]):
            return "C"
        return "A"
    return "B"                                       # absent from the whole corpus


def evaluate_generation(generated_ttl: str, q: Question, system: str) -> HallucinationReport:
    g = Graph()
    try:
        from llm_generator import extract_turtle
        g.parse(data=extract_turtle(generated_ttl), format="turtle")
    except Exception:
        return HallucinationReport(holon_id=q.holon_id, system=system)

    grounded_pairs = {(f["s"], f["o"]) for f in q.facts}
    grounded_eff = {(f["s"], f["o"]): f.get("effectiveness") for f in q.facts}
    asserted = extract_asserted(g)

    rep = HallucinationReport(holon_id=q.holon_id, system=system,
                              n_assertions=len(asserted))
    labels = []
    for (s, o, e) in asserted:
        lab = classify_fact((s, o), e, grounded_pairs, grounded_eff)
        labels.append(lab)
        rep.details.append({"drug": _local(s), "disease": _local(o),
                            "effectiveness": e, "label": lab})
        if lab == "grounded":
            rep.grounded += 1
        elif lab == "A":
            rep.type_a += 1
        elif lab == "B":
            rep.type_b += 1
        elif lab == "C":
            rep.type_c += 1

    covered = {(s, o) for (s, o, _) in asserted} & grounded_pairs
    rep.coverage = len(covered) / len(grounded_pairs) if grounded_pairs else 0.0
    rep.precision_at_1 = _precision_at(labels, 1)
    rep.precision_at_3 = _precision_at(labels, 3)
    return rep


def _precision_at(labels: list, k: int) -> float:
    if not labels:
        return 0.0
    top = labels[:k]
    return sum(1 for l in top if l == "grounded") / len(top)


# --------------------------------------------------------------------------- #
# Inter-annotator agreement
# --------------------------------------------------------------------------- #

def cohens_kappa(a: list, b: list) -> float:
    """Cohen's kappa between two equal-length label sequences."""
    if not a or len(a) != len(b):
        return float("nan")
    n = len(a)
    cats = sorted(set(a) | set(b))
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum((ca[c] / n) * (cb[c] / n) for c in cats)
    return 1.0 if pe >= 1.0 else (po - pe) / (1 - pe)


def _local(uri) -> str:
    return str(uri).rsplit("/", 1)[-1].rsplit("#", 1)[-1]


def main() -> None:
    """Demo classifier on hand-crafted A/B/C/grounded inputs."""
    from dataset import load_testset
    q = load_testset()[0]
    drug, dis, src = q.facts[0]["s"], q.facts[0]["o"], q.facts[0]["source"]
    ttl = f"""@prefix holon: <https://example.org/holon#> .
@prefix oe: <https://example.org/openevidence#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
<{drug}> oe:treats <{dis}> .
<g:ev0> a holon:EvidenceAssertion ; rdf:reifies <g:tt0> ; oe:effectiveness "effective" .
<g:tt0> rdf:subject <{drug}> ; rdf:predicate oe:treats ; rdf:object <{dis}> .
<https://example.org/openevidence/drugs/fabricatedX> oe:treats <{dis}> ."""
    rep = evaluate_generation(ttl, q, "demo")
    print(f"asserted={rep.n_assertions} grounded={rep.grounded} "
          f"A={rep.type_a} B={rep.type_b} C={rep.type_c} "
          f"halluc_rate={rep.hallucination_rate:.2f} coverage={rep.coverage:.2f}")
    for d in rep.details:
        print("  ", d)
    print("kappa(self,self) =", cohens_kappa(["grounded", "A", "B"], ["grounded", "A", "B"]))
    print("kappa(2 disagree) =", round(cohens_kappa(
        ["grounded", "A", "B", "grounded"], ["grounded", "A", "A", "grounded"]), 3))


if __name__ == "__main__":
    main()
