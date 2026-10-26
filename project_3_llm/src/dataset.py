"""dataset.py — load Project 1's holonic corpus and build the 100-question
test set with gold-standard grounding (§3.2/§3.3 data foundation).

A question's *gold standard* is the holon itself: its `oe:questionText`, its
`oe:answerText`, and the grounded facts asserted in its interior (each a reified
`drug oe:treats disease` with confidence, level, cited source, effectiveness).
Hallucination is later measured against exactly these grounded facts + the cited
sources (see evaluation.py / theory/hallucination_taxonomy.md).

Deterministic: a fixed seed makes the 100-question split reproducible.
"""
from __future__ import annotations

import json
import random
import sys
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Optional

from rdflib import Graph, URIRef
from rdflib.namespace import RDF, RDFS

_SRC = Path(__file__).resolve().parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
from namespaces import OE, SPARQL_PREFIXES, bind_all  # noqa: E402

_PROJ = _SRC.parent
_REPO = _SRC.parents[1]
CORPUS_TTL = _REPO / "project_1_crawling" / "data" / "rdf" / "holonic" / "all_holonic.ttl"
QUESTIONS_DIR = _PROJ / "data" / "questions"
TESTSET_JSON = QUESTIONS_DIR / "testset.json"

DEFAULT_N = 100
SEED = 42


@dataclass
class Fact:
    s: str                 # drug URI
    o: str                 # disease URI
    confidence: float
    level: str
    source: str            # evidence source URI
    effectiveness: Optional[str] = None


@dataclass
class Question:
    holon_id: str
    holon_uri: str
    question: str
    gold_answer: str
    specialty: str
    disease: Optional[str]
    facts: list = field(default_factory=list)         # list[Fact-as-dict]
    source_pmids: list = field(default_factory=list)

    def fact_objs(self) -> list:
        return [Fact(**f) for f in self.facts]


@lru_cache(maxsize=1)
def load_corpus() -> Graph:
    """Parse the merged Model-A corpus once (entities + holons + assertions)."""
    g = Graph()
    bind_all(g)
    g.parse(CORPUS_TTL, format="turtle")
    return g


_Q_HOLONS = SPARQL_PREFIXES + """
SELECT ?h ?q ?a ?spec ?disease WHERE {
  ?h a holon:ClinicalQuestionHolon ;
     oe:questionText ?q ;
     oe:answerText ?a .
  OPTIONAL { ?h oe:belongsToSpecialty ?spec }
  OPTIONAL { ?h oe:aboutDisease ?disease }
} ORDER BY ?h
"""

_Q_FACTS = SPARQL_PREFIXES + """
SELECT ?conf ?level ?drug ?disease ?src ?eff WHERE {
  ?ev a holon:EvidenceAssertion ;
      holon:inHolon ?holon ;
      holon:confidence ?conf ;
      holon:evidenceLevel ?level ;
      oe:cites ?src ;
      rdf:reifies ?tt .
  ?tt rdf:subject ?drug ; rdf:object ?disease .
  OPTIONAL { ?ev oe:effectiveness ?eff }
} ORDER BY ?drug ?src
"""


def _facts_for(g: Graph, holon: URIRef) -> list:
    out = []
    for r in g.query(_Q_FACTS, initBindings={"holon": holon}):
        out.append(Fact(
            s=str(r.drug), o=str(r.disease), confidence=float(r.conf),
            level=str(r.level), source=str(r.src),
            effectiveness=(str(r.eff) if r.eff is not None else None),
        ))
    # Deterministic de-dup (same drug-disease-source).
    seen, uniq = set(), []
    for f in out:
        key = (f.s, f.o, f.source)
        if key not in seen:
            seen.add(key)
            uniq.append(f)
    return uniq


def extract_questions(g: Optional[Graph] = None) -> list:
    """Holons carrying at least one complete grounded fact whose `oe:treats`
    object is a declared `oe:Disease`.

    Project 1 also reified a few `drug oe:treats <symptom>` edges (e.g. metoprolol
    'treats' chest_pain in _safety holons). Those violate the ontology's
    `oe:treats` range (Disease) independently of any system, so they are excluded
    here to keep the controlled experiment about treatment evidence; the
    exclusion is documented in the README Threats to Validity.
    """
    g = g or load_corpus()
    questions = []
    for r in g.query(_Q_HOLONS):
        holon = r.h
        facts = [f for f in _facts_for(g, holon)
                 if (URIRef(f.o), RDF.type, OE.Disease) in g]
        if not facts:
            continue
        pmids = sorted({_local(f.source) for f in facts})
        questions.append(Question(
            holon_id=_local(holon), holon_uri=str(holon),
            question=str(r.q), gold_answer=str(r.a),
            specialty=(str(r.spec) if r.spec is not None else "General Medicine"),
            disease=(str(r.disease) if r.disease is not None else None),
            facts=[asdict(f) for f in facts], source_pmids=pmids,
        ))
    questions.sort(key=lambda q: q.holon_id)
    return questions


def build_testset(n: int = DEFAULT_N, seed: int = SEED,
                  write: bool = True) -> list:
    """Deterministic n-question sample written to data/questions/testset.json."""
    allq = extract_questions()
    rng = random.Random(seed)
    rng.shuffle(allq)
    chosen = allq[:n]
    chosen.sort(key=lambda q: q.holon_id)
    if write:
        QUESTIONS_DIR.mkdir(parents=True, exist_ok=True)
        TESTSET_JSON.write_text(json.dumps([asdict(q) for q in chosen], indent=2))
    return chosen


def load_testset() -> list:
    if not TESTSET_JSON.exists():
        return build_testset()
    raw = json.loads(TESTSET_JSON.read_text())
    return [Question(**q) for q in raw]


def grounding_graph_for(q: Question, g: Optional[Graph] = None) -> Graph:
    """Typed entity/source subgraph for a question, so referential SHACL
    (oe:cites -> EvidenceSource, oe:treats -> Disease) can run over generated RDF.
    """
    g = g or load_corpus()
    out = Graph()
    bind_all(out)
    uris = set()
    for f in q.facts:
        uris |= {URIRef(f["s"]), URIRef(f["o"]), URIRef(f["source"])}
    for u in uris:
        for p, o in g.predicate_objects(u):
            if p in (RDF.type, RDFS.label, OE.pubmedId, OE.publicationDate,
                     OE.icdCode, OE.atcCode, OE.doi, OE.evidenceLevelLabel):
                out.add((u, p, o))
    return out


def corpus_facts_by_disease(g: Optional[Graph] = None) -> dict:
    """disease URI -> list[Fact] across the whole corpus (used by the naive
    retriever to over-fetch loosely related, ungrounded candidate triples)."""
    g = g or load_corpus()
    by_disease: dict = {}
    for r in g.query(_Q_FACTS):
        f = Fact(s=str(r.drug), o=str(r.disease), confidence=float(r.conf),
                 level=str(r.level), source=str(r.src),
                 effectiveness=(str(r.eff) if r.eff is not None else None))
        by_disease.setdefault(f.o, []).append(f)
    return by_disease


def _local(uri) -> str:
    return str(uri).rsplit("/", 1)[-1].rsplit("#", 1)[-1]


def main() -> None:
    qs = build_testset()
    n_facts = sum(len(q.facts) for q in qs)
    specialties = sorted({q.specialty for q in qs})
    print(f"Test set: {len(qs)} questions, {n_facts} grounded facts -> {TESTSET_JSON}")
    print(f"Specialties ({len(specialties)}): {', '.join(specialties)}")
    print(f"Avg facts/question: {n_facts/len(qs):.2f}")
    print("Example:", qs[0].holon_id, "|", qs[0].question[:70])


if __name__ == "__main__":
    main()
