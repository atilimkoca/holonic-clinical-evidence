"""neo4j_query.py — natural-language query interface (API contract + Difficulty D).

Implements the shared API contract:

    from project_3_llm.src.neo4j_query import natural_language_query
    result = natural_language_query("What drugs treat hypertension with Level 1A evidence?",
                                    max_hops=3, include_confidence=True)

The question is translated to BOTH SPARQL and Cypher. By default it executes the
SPARQL over Project 1's holonic corpus with rdflib (offline, no DB needed) and
also emits the equivalent Cypher. If `NEO4J_URI` is set and the `neo4j` driver is
installed, it runs the Cypher against the live database instead (graceful
degradation otherwise — same pattern as Project 1).
"""
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Optional

from rdflib import URIRef
from rdflib.namespace import RDFS

_SRC = Path(__file__).resolve().parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from namespaces import OE, SPARQL_PREFIXES                  # noqa: E402
from dataset import load_corpus                              # noqa: E402

LEVELS = ["Level-1A", "Level-1B", "Level-2A", "Level-2B", "Level-3", "Level-4", "Level-5"]


@dataclass
class QueryResult:
    question: str
    sparql: str
    cypher: str
    backend: str
    results: list = field(default_factory=list)

    def __repr__(self) -> str:
        return (f"QueryResult(backend={self.backend}, n={len(self.results)}, "
                f"top={self.results[:3]})")


# --------------------------------------------------------------------------- #
# Lightweight NL parsing (deterministic, corpus-grounded)
# --------------------------------------------------------------------------- #

@lru_cache(maxsize=1)
def _label_index() -> dict:
    """disease/drug label (lowercased) -> URI, from the corpus."""
    g = load_corpus()
    idx = {}
    for cls in (OE.Disease, OE.Drug):
        for s in g.subjects(predicate=None, object=cls):
            pass
    # collect by rdf:type
    from rdflib.namespace import RDF
    for s, _, o in g.triples((None, RDF.type, None)):
        if o in (OE.Disease, OE.Drug):
            label = g.value(s, RDFS.label)
            key = str(label).lower() if label else _local(s).replace("_", " ").lower()
            idx[key] = (str(s), "Disease" if o == OE.Disease else "Drug")
            idx[_local(s).replace("_", " ").lower()] = (str(s),
                                                        "Disease" if o == OE.Disease else "Drug")
    return idx


def _match_entity(question: str, kind: str) -> Optional[str]:
    q = question.lower()
    best = None
    for label, (uri, k) in _label_index().items():
        if k == kind and label and label in q:
            if best is None or len(label) > best[1]:
                best = (uri, len(label))
    return best[0] if best else None


def _match_level(question: str) -> Optional[str]:
    q = question.lower().replace(" ", "")
    for lv in LEVELS:
        if lv.lower().replace("-", "").replace(" ", "") in q:
            return lv
    m = re.search(r"level\s*-?\s*([12][ab]?|[345])", question, re.I)
    if m:
        cand = "Level-" + m.group(1).upper()
        return cand if cand in LEVELS else None
    return None


# --------------------------------------------------------------------------- #
# Query construction
# --------------------------------------------------------------------------- #

def _build_sparql(disease_uri: Optional[str], drug_uri: Optional[str],
                  level: Optional[str], include_conf: bool) -> str:
    filt = []
    if disease_uri:
        filt.append(f"  ?tt rdf:object <{disease_uri}> .")
    if drug_uri:
        filt.append(f"  ?tt rdf:subject <{drug_uri}> .")
    if level:
        filt.append(f'  FILTER(?level = "{level}")')
    sel = "?drug ?disease ?level" + (" ?conf ?src" if include_conf else "")
    body = "\n".join(filt)
    return (SPARQL_PREFIXES + f"""
SELECT DISTINCT {sel} WHERE {{
  ?ev a holon:EvidenceAssertion ;
      rdf:reifies ?tt ;
      holon:evidenceLevel ?level ;
      holon:confidence ?conf ;
      oe:cites ?src .
  ?tt rdf:subject ?drug ; rdf:predicate oe:treats ; rdf:object ?disease .
{body}
}} ORDER BY DESC(?conf) LIMIT 25""")


def _build_cypher(disease_uri: Optional[str], drug_uri: Optional[str],
                  level: Optional[str], include_conf: bool, max_hops: int) -> str:
    where = []
    if disease_uri:
        where.append(f"dis.uri = '{disease_uri}'")
    if drug_uri:
        where.append(f"drug.uri = '{drug_uri}'")
    if level:
        where.append(f"a.evidenceLevel = '{level}'")
    where_s = ("WHERE " + " AND ".join(where)) if where else ""
    ret = "drug.label AS drug, dis.label AS disease, a.evidenceLevel AS level"
    if include_conf:
        ret += ", a.confidence AS confidence, src.pubmedId AS source"
    return (f"MATCH (drug:Drug)-[:ASSERTS]->(a:EvidenceAssertion)-"
            f"[:REIFIES*1..{max_hops}]->(:Triple)-[:OBJECT]->(dis:Disease)\n"
            f"MATCH (a)-[:CITES]->(src:EvidenceSource)\n"
            f"{where_s}\nRETURN {ret}\nORDER BY a.confidence DESC LIMIT 25")


# --------------------------------------------------------------------------- #
# Execution
# --------------------------------------------------------------------------- #

def _run_sparql(sparql: str, include_conf: bool) -> list:
    g = load_corpus()
    out = []
    for r in g.query(sparql):
        row = {"drug": _local(r.drug), "disease": _local(r.disease),
               "level": str(r.level)}
        if include_conf:
            row["confidence"] = float(r.conf)
            row["source"] = _local(r.src)
        out.append(row)
    return out


def _run_neo4j(cypher: str) -> Optional[list]:
    uri = os.environ.get("NEO4J_URI")
    if not uri:
        return None
    try:
        from neo4j import GraphDatabase
    except ImportError:
        return None
    try:
        drv = GraphDatabase.driver(uri, auth=(os.environ.get("NEO4J_USER", "neo4j"),
                                              os.environ.get("NEO4J_PASS", "")))
        with drv.session(database=os.environ.get("NEO4J_DB", "openevidence")) as s:
            return [dict(rec) for rec in s.run(cypher)]
    except Exception:
        return None


def natural_language_query(question: str, max_hops: int = 3,
                           include_confidence: bool = True) -> QueryResult:
    """Translate NL -> SPARQL/Cypher, execute (Neo4J if available, else rdflib)."""
    disease = _match_entity(question, "Disease")
    drug = _match_entity(question, "Drug")
    level = _match_level(question)
    sparql = _build_sparql(disease, drug, level, include_confidence)
    cypher = _build_cypher(disease, drug, level, include_confidence, max_hops)

    live = _run_neo4j(cypher)
    if live is not None:
        return QueryResult(question, sparql, cypher, "neo4j", live)
    return QueryResult(question, sparql, cypher, "rdflib",
                       _run_sparql(sparql, include_confidence))


def _local(uri) -> str:
    return str(uri).rsplit("/", 1)[-1].rsplit("#", 1)[-1]


def main() -> None:
    for qtext in [
        "What drugs treat hypertension with Level 1A evidence?",
        "What is the recommended treatment for acute kidney injury?",
        "Which drugs treat epilepsy?",
    ]:
        res = natural_language_query(qtext)
        print(f"\nQ: {qtext}")
        print(f"backend={res.backend}, results={len(res.results)}")
        for row in res.results[:4]:
            print("   ", row)


if __name__ == "__main__":
    main()
