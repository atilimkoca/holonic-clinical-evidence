"""benchmark_queries.py — the 50-query expressiveness benchmark (assignment §1.3).

Each query is authored twice: ``a`` runs on Model A (holonic dataset, named
graphs + materialised RDF 1.2 reification) and ``b`` runs on Model B (flat
RDF 1.1, standard rdf:Statement reification, single graph). When a query cannot
be expressed over Model B *as data* (because the flat model does not record the
holon-layer partition — there are no named graphs and layer membership is not a
triple), ``b`` is ``None`` with a recorded justification.

Categories (assignment §1.3):
  simple  (15) — single triple-pattern lookups over base relations
  medium  (15) — multi-hop and/or reification access
  complex (10) — temporal + provenance + confidence filtering
  hard    (10) — holon-layer / named-graph identity queries (Model-A only)

Fields:
  id, category, desc, kind ("select"|"ask"),
  a  : SPARQL for Model A,
  b  : SPARQL for Model B or None,
  b_unanswerable_reason : str (when b is None),
  patterns_a, patterns_b : authored triple-pattern counts (for the complexity metric),
  compare : whether A and B result sets are expected to be identical,
  cypher  : optional Cypher equivalent for the Neo4j path (informational).
"""
from __future__ import annotations

PREFIXES = """
PREFIX rdf:   <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd:   <http://www.w3.org/2001/XMLSchema#>
PREFIX prov:  <http://www.w3.org/ns/prov#>
PREFIX holon: <https://example.org/holon#>
PREFIX oe:    <https://example.org/openevidence#>
PREFIX oeq:   <https://example.org/openevidence/questions/>
PREFIX oed:   <https://example.org/openevidence/diseases/>
PREFIX oedrug:<https://example.org/openevidence/drugs/>
PREFIX oesrc: <https://example.org/openevidence/sources/>
PREFIX oeevt: <https://example.org/openevidence/events/>
PREFIX oespec:<https://example.org/openevidence/specialties/>
PREFIX oesym: <https://example.org/openevidence/symptoms/>
"""

QUERIES: list[dict] = []


def _q(**kw) -> None:
    kw.setdefault("kind", "select")
    kw.setdefault("b", None)
    kw.setdefault("b_unanswerable_reason", "")
    kw.setdefault("compare", True)
    kw.setdefault("cypher", "")
    kw.setdefault("patterns_b", 0)
    QUERIES.append(kw)


# =============================================================================
# SIMPLE (15) — single-hop lookups over base relations; identical in both models
# =============================================================================
_q(id="S01", category="simple", desc="All diseases (typed oe:Disease).",
   a="SELECT ?d WHERE { ?d a oe:Disease }",
   b="SELECT ?d WHERE { ?d a oe:Disease }", patterns_a=1, patterns_b=1,
   cypher="MATCH (d:Disease) RETURN d")
_q(id="S02", category="simple", desc="All drugs.",
   a="SELECT ?x WHERE { ?x a oe:Drug }", b="SELECT ?x WHERE { ?x a oe:Drug }",
   patterns_a=1, patterns_b=1)
_q(id="S03", category="simple", desc="ICD code of hypertension.",
   a="SELECT ?c WHERE { oed:hypertension oe:icdCode ?c }",
   b="SELECT ?c WHERE { oed:hypertension oe:icdCode ?c }", patterns_a=1, patterns_b=1)
_q(id="S04", category="simple", desc="ATC code of lisinopril.",
   a="SELECT ?c WHERE { oedrug:lisinopril oe:atcCode ?c }",
   b="SELECT ?c WHERE { oedrug:lisinopril oe:atcCode ?c }", patterns_a=1, patterns_b=1)
_q(id="S05", category="simple", desc="Drugs that treat hypertension (base triple).",
   a="SELECT ?x WHERE { ?x oe:treats oed:hypertension }",
   b="SELECT ?x WHERE { ?x oe:treats oed:hypertension }", patterns_a=1, patterns_b=1)
_q(id="S06", category="simple", desc="Symptoms of hypertension.",
   a="SELECT ?s WHERE { oed:hypertension oe:hasSymptom ?s }",
   b="SELECT ?s WHERE { oed:hypertension oe:hasSymptom ?s }", patterns_a=1, patterns_b=1)
_q(id="S07", category="simple", desc="All evidence sources.",
   a="SELECT ?s WHERE { ?s a oe:EvidenceSource }",
   b="SELECT ?s WHERE { ?s a oe:EvidenceSource }", patterns_a=1, patterns_b=1)
_q(id="S08", category="simple", desc="All clinical-question holons.",
   a="SELECT ?h WHERE { ?h a holon:ClinicalQuestionHolon }",
   b="SELECT ?h WHERE { ?h a holon:ClinicalQuestionHolon }", patterns_a=1, patterns_b=1)
_q(id="S09", category="simple", desc="Drug classes present.",
   a="SELECT DISTINCT ?c WHERE { ?x oe:drugClass ?c }",
   b="SELECT DISTINCT ?c WHERE { ?x oe:drugClass ?c }", patterns_a=1, patterns_b=1)
_q(id="S10", category="simple", desc="Diseases in the Cardiology specialty.",
   a="SELECT ?d WHERE { ?d oe:inSpecialty oespec:Cardiology }",
   b="SELECT ?d WHERE { ?d oe:inSpecialty oespec:Cardiology }", patterns_a=1, patterns_b=1)
_q(id="S11", category="simple", desc="PubMed IDs of all systematic reviews.",
   a="SELECT ?p WHERE { ?s a oe:SystematicReview ; oe:pubmedId ?p }",
   b="SELECT ?p WHERE { ?s a oe:SystematicReview ; oe:pubmedId ?p }", patterns_a=2, patterns_b=2)
_q(id="S12", category="simple", desc="Approval date of metformin.",
   a="SELECT ?d WHERE { oedrug:metformin oe:approvalDate ?d }",
   b="SELECT ?d WHERE { oedrug:metformin oe:approvalDate ?d }", patterns_a=1, patterns_b=1)
_q(id="S13", category="simple", desc="Count of clinical-question holons.", kind="select",
   a="SELECT (COUNT(?h) AS ?n) WHERE { ?h a holon:ClinicalQuestionHolon }",
   b="SELECT (COUNT(?h) AS ?n) WHERE { ?h a holon:ClinicalQuestionHolon }",
   patterns_a=1, patterns_b=1)
_q(id="S14", category="simple", desc="Specialties (typed oe:Specialty).",
   a="SELECT ?s WHERE { ?s a oe:Specialty }",
   b="SELECT ?s WHERE { ?s a oe:Specialty }", patterns_a=1, patterns_b=1)
_q(id="S15", category="simple", desc="Does any drug treat hypertension? (ASK)", kind="ask",
   a="ASK { ?x oe:treats oed:hypertension }",
   b="ASK { ?x oe:treats oed:hypertension }", patterns_a=1, patterns_b=1)

# =============================================================================
# MEDIUM (15) — multi-hop and reification access. Answerable in both, but the
# flat model needs the verbose rdf:Statement pattern (higher patterns_b).
# =============================================================================
_q(id="M01", category="medium",
   desc="Confidence of each treats-assertion (edge-level metadata).",
   a="""SELECT ?s ?o ?conf WHERE {
         ?r a holon:EvidenceAssertion ; rdf:reifies ?tt ; holon:confidence ?conf .
         ?tt rdf:subject ?s ; rdf:predicate oe:treats ; rdf:object ?o }""",
   b="""SELECT ?s ?o ?conf WHERE {
         ?r a rdf:Statement ; rdf:subject ?s ; rdf:predicate oe:treats ;
            rdf:object ?o ; holon:confidence ?conf }""",
   patterns_a=5, patterns_b=5,
   cypher="MATCH (:Drug)-[t:treats]->(:Disease) RETURN t.confidence")
_q(id="M02", category="medium", desc="Assertions with evidence level Level-1A.",
   a="""SELECT ?r WHERE { ?r a holon:EvidenceAssertion ; holon:evidenceLevel "Level-1A" }""",
   b="""SELECT ?r WHERE { ?r a rdf:Statement ; holon:evidenceLevel "Level-1A" }""",
   patterns_a=2, patterns_b=2)
_q(id="M03", category="medium", desc="Drug-disease pairs asserted with confidence > 0.9.",
   a="""SELECT ?s ?o WHERE {
         ?r a holon:EvidenceAssertion ; rdf:reifies ?tt ; holon:confidence ?c .
         ?tt rdf:subject ?s ; rdf:predicate oe:treats ; rdf:object ?o . FILTER(?c > 0.9) }""",
   b="""SELECT ?s ?o WHERE {
         ?r a rdf:Statement ; rdf:subject ?s ; rdf:predicate oe:treats ;
            rdf:object ?o ; holon:confidence ?c . FILTER(?c > 0.9) }""",
   patterns_a=5, patterns_b=5)
_q(id="M04", category="medium", desc="Sources cited by each evidence assertion.",
   a="""SELECT ?r ?src WHERE { ?r a holon:EvidenceAssertion ; oe:cites ?src }""",
   b="""SELECT ?r ?src WHERE { ?r a rdf:Statement ; oe:cites ?src }""",
   patterns_a=2, patterns_b=2)
_q(id="M05", category="medium", desc="Holons about diseases in Cardiology (2-hop join).",
   a="""SELECT ?h WHERE { ?h a holon:ClinicalQuestionHolon ; oe:aboutDisease ?d .
         ?d oe:inSpecialty oespec:Cardiology }""",
   b="""SELECT ?h WHERE { ?h a holon:ClinicalQuestionHolon ; oe:aboutDisease ?d .
         ?d oe:inSpecialty oespec:Cardiology }""", patterns_a=3, patterns_b=3)
_q(id="M06", category="medium", desc="Drugs treating a disease that has the symptom 'fatigue'.",
   a="""SELECT DISTINCT ?drug WHERE { ?drug oe:treats ?d . ?d oe:hasSymptom oesym:fatigue }""",
   b="""SELECT DISTINCT ?drug WHERE { ?drug oe:treats ?d . ?d oe:hasSymptom oesym:fatigue }""",
   patterns_a=2, patterns_b=2)
_q(id="M07", category="medium", desc="Evidence assertions and their owning holon.",
   a="""SELECT ?r ?h WHERE { ?r a holon:EvidenceAssertion ; holon:inHolon ?h }""",
   b="""SELECT ?r ?h WHERE { ?r a rdf:Statement ; holon:inHolon ?h }""",
   patterns_a=2, patterns_b=2)
_q(id="M08", category="medium", desc="Confidence of treats(lisinopril, hypertension).",
   a="""SELECT ?c WHERE { ?r rdf:reifies ?tt ; holon:confidence ?c .
         ?tt rdf:subject oedrug:lisinopril ; rdf:predicate oe:treats ; rdf:object oed:hypertension }""",
   b="""SELECT ?c WHERE { ?r a rdf:Statement ; rdf:subject oedrug:lisinopril ;
         rdf:predicate oe:treats ; rdf:object oed:hypertension ; holon:confidence ?c }""",
   patterns_a=5, patterns_b=5)
_q(id="M09", category="medium", desc="Distinct evidence levels used across assertions.",
   a="""SELECT DISTINCT ?lvl WHERE { ?r a holon:EvidenceAssertion ; holon:evidenceLevel ?lvl }""",
   b="""SELECT DISTINCT ?lvl WHERE { ?r a rdf:Statement ; holon:evidenceLevel ?lvl }""",
   patterns_a=2, patterns_b=2)
_q(id="M10", category="medium", desc="Side-effect assertions (drug causesSideEffect symptom).",
   a="""SELECT ?s ?o WHERE { ?r rdf:reifies ?tt . ?tt rdf:subject ?s ;
         rdf:predicate oe:causesSideEffect ; rdf:object ?o }""",
   b="""SELECT ?s ?o WHERE { ?r a rdf:Statement ; rdf:subject ?s ;
         rdf:predicate oe:causesSideEffect ; rdf:object ?o }""",
   patterns_a=4, patterns_b=4)
_q(id="M11", category="medium", desc="Holons citing at least one source (interior cites).",
   a="""SELECT DISTINCT ?h WHERE { ?h a holon:ClinicalQuestionHolon ; oe:cites ?s }""",
   b="""SELECT DISTINCT ?h WHERE { ?h a holon:ClinicalQuestionHolon ; oe:cites ?s }""",
   patterns_a=2, patterns_b=2)
_q(id="M12", category="medium", desc="Drugs and the classes contraindicated against them.",
   a="""SELECT ?a ?b WHERE { ?a oe:contraindicatedWith ?b }""",
   b="""SELECT ?a ?b WHERE { ?a oe:contraindicatedWith ?b }""", patterns_a=1, patterns_b=1)
_q(id="M13", category="medium", desc="Count of evidence assertions per evidence level.",
   a="""SELECT ?lvl (COUNT(?r) AS ?n) WHERE {
         ?r a holon:EvidenceAssertion ; holon:evidenceLevel ?lvl } GROUP BY ?lvl""",
   b="""SELECT ?lvl (COUNT(?r) AS ?n) WHERE {
         ?r a rdf:Statement ; holon:evidenceLevel ?lvl } GROUP BY ?lvl""",
   patterns_a=2, patterns_b=2)
_q(id="M14", category="medium", desc="Disease holons containing a given clinical-question holon.",
   a="""SELECT ?dh WHERE { ?dh a holon:DiseaseHolon ; holon:containsHolon oeq:q_hypertension_treatment }""",
   b="""SELECT ?dh WHERE { ?dh a holon:DiseaseHolon ; holon:containsHolon oeq:q_hypertension_treatment }""",
   patterns_a=2, patterns_b=2)
_q(id="M15", category="medium", desc="Is there a Level-1A assertion with confidence >= 0.9? (ASK)",
   kind="ask",
   a="""ASK { ?r a holon:EvidenceAssertion ; holon:evidenceLevel "Level-1A" ; holon:confidence ?c .
         FILTER(?c >= 0.9) }""",
   b="""ASK { ?r a rdf:Statement ; holon:evidenceLevel "Level-1A" ; holon:confidence ?c .
         FILTER(?c >= 0.9) }""", patterns_a=3, patterns_b=3)

# =============================================================================
# COMPLEX (10) — temporal + provenance + confidence. Answerable in both.
# =============================================================================
_q(id="C01", category="complex",
   desc="Assertions recorded after 2020 citing a systematic review, confidence > 0.9.",
   a="""SELECT ?r ?c WHERE {
         ?r a holon:EvidenceAssertion ; holon:confidence ?c ; holon:recordedOn ?d ; oe:cites ?src .
         ?src a oe:SystematicReview . FILTER(?c > 0.9 && ?d > "2020-01-01"^^xsd:date) }""",
   b="""SELECT ?r ?c WHERE {
         ?r a rdf:Statement ; holon:confidence ?c ; holon:recordedOn ?d ; oe:cites ?src .
         ?src a oe:SystematicReview . FILTER(?c > 0.9 && ?d > "2020-01-01"^^xsd:date) }""",
   patterns_a=5, patterns_b=5)
_q(id="C02", category="complex",
   desc="Drugs approved after 2000 that treat a disease first described before 1950 (temporal join).",
   a="""SELECT ?drug ?dis WHERE { ?drug oe:treats ?dis ; oe:approvalDate ?ad .
         ?dis oe:firstDescribedDate ?fd .
         FILTER(?ad > "2000-01-01"^^xsd:date && ?fd < "1950-01-01"^^xsd:date) }""",
   b="""SELECT ?drug ?dis WHERE { ?drug oe:treats ?dis ; oe:approvalDate ?ad .
         ?dis oe:firstDescribedDate ?fd .
         FILTER(?ad > "2000-01-01"^^xsd:date && ?fd < "1950-01-01"^^xsd:date) }""",
   patterns_a=3, patterns_b=3, compare=True)
_q(id="C03", category="complex", desc="Provenance: holons attributed to the AI agent.",
   a="""SELECT ?h WHERE { ?h prov:wasAttributedTo oeq:openevidence_ai }""",
   b="""SELECT ?h WHERE { ?h prov:wasAttributedTo oeq:openevidence_ai }""",
   patterns_a=1, patterns_b=1)
_q(id="C04", category="complex", desc="Five most-cited sources (by number of citing holons).",
   a="""SELECT ?src (COUNT(?h) AS ?n) WHERE { ?h a holon:ClinicalQuestionHolon ; oe:cites ?src }
         GROUP BY ?src ORDER BY DESC(?n) ?src LIMIT 5""",
   b="""SELECT ?src (COUNT(?h) AS ?n) WHERE { ?h a holon:ClinicalQuestionHolon ; oe:cites ?src }
         GROUP BY ?src ORDER BY DESC(?n) ?src LIMIT 5""", patterns_a=2, patterns_b=2)
_q(id="C05", category="complex",
   desc="High-confidence (>0.9) treats-assertions whose source is a meta-analysis or RCT.",
   a="""SELECT ?s ?o WHERE {
         ?r a holon:EvidenceAssertion ; rdf:reifies ?tt ; holon:confidence ?c ; oe:cites ?src .
         ?tt rdf:subject ?s ; rdf:predicate oe:treats ; rdf:object ?o .
         { ?src a oe:MetaAnalysis } UNION { ?src a oe:ClinicalTrial } FILTER(?c > 0.9) }""",
   b="""SELECT ?s ?o WHERE {
         ?r a rdf:Statement ; rdf:subject ?s ; rdf:predicate oe:treats ; rdf:object ?o ;
            holon:confidence ?c ; oe:cites ?src .
         { ?src a oe:MetaAnalysis } UNION { ?src a oe:ClinicalTrial } FILTER(?c > 0.9) }""",
   patterns_a=8, patterns_b=8)
_q(id="C06", category="complex",
   desc="Mean assertion confidence per evidence level.",
   a="""SELECT ?lvl (AVG(?c) AS ?avg) WHERE {
         ?r a holon:EvidenceAssertion ; holon:evidenceLevel ?lvl ; holon:confidence ?c }
         GROUP BY ?lvl ORDER BY ?lvl""",
   b="""SELECT ?lvl (AVG(?c) AS ?avg) WHERE {
         ?r a rdf:Statement ; holon:evidenceLevel ?lvl ; holon:confidence ?c }
         GROUP BY ?lvl ORDER BY ?lvl""", patterns_a=3, patterns_b=3)
_q(id="C07", category="complex",
   desc="Assertions whose recording date is at/after the cited source's publication date "
        "(temporal consistency witness).",
   a="""SELECT ?r WHERE {
         ?r a holon:EvidenceAssertion ; holon:recordedOn ?rd ; oe:cites ?src .
         ?src oe:publicationDate ?pd . FILTER(?rd >= ?pd) }""",
   b="""SELECT ?r WHERE {
         ?r a rdf:Statement ; holon:recordedOn ?rd ; oe:cites ?src .
         ?src oe:publicationDate ?pd . FILTER(?rd >= ?pd) }""", patterns_a=4, patterns_b=4)
_q(id="C08", category="complex",
   desc="Drug treating the most distinct diseases (with high-confidence evidence).",
   a="""SELECT ?drug (COUNT(DISTINCT ?o) AS ?n) WHERE {
         ?r a holon:EvidenceAssertion ; rdf:reifies ?tt ; holon:confidence ?c .
         ?tt rdf:subject ?drug ; rdf:predicate oe:treats ; rdf:object ?o . FILTER(?c >= 0.85) }
         GROUP BY ?drug ORDER BY DESC(?n) LIMIT 5""",
   b="""SELECT ?drug (COUNT(DISTINCT ?o) AS ?n) WHERE {
         ?r a rdf:Statement ; rdf:subject ?drug ; rdf:predicate oe:treats ; rdf:object ?o ;
            holon:confidence ?c . FILTER(?c >= 0.85) }
         GROUP BY ?drug ORDER BY DESC(?n) LIMIT 5""", patterns_a=5, patterns_b=5)
_q(id="C09", category="complex",
   desc="Holons generated after 2024 (provenance dateTime).",
   a="""SELECT ?h WHERE { ?h prov:generatedAtTime ?t . FILTER(?t > "2024-01-01T00:00:00Z"^^xsd:dateTime) }""",
   b="""SELECT ?h WHERE { ?h prov:generatedAtTime ?t . FILTER(?t > "2024-01-01T00:00:00Z"^^xsd:dateTime) }""",
   patterns_a=1, patterns_b=1, compare=True)
_q(id="C10", category="complex",
   desc="Evidence assertions citing a source published before 2015 (legacy evidence).",
   a="""SELECT ?r WHERE { ?r a holon:EvidenceAssertion ; oe:cites ?src .
         ?src oe:publicationDate ?pd . FILTER(?pd < "2015-01-01"^^xsd:date) }""",
   b="""SELECT ?r WHERE { ?r a rdf:Statement ; oe:cites ?src .
         ?src oe:publicationDate ?pd . FILTER(?pd < "2015-01-01"^^xsd:date) }""",
   patterns_a=3, patterns_b=3)

# =============================================================================
# HARD (10) — holon-layer / named-graph identity. Model-A only: the flat model
# does not record the layer partition as data (no named graphs, no layer triple),
# so these are not answerable over Model B without re-modelling it (which would
# make it non-flat). See theory/expressiveness.md.
# =============================================================================
_NG_REASON = ("Flat RDF 1.1 has no named graphs and does not record holon-layer "
              "membership as a triple; the query ranges over graph/layer identity, "
              "which is not present in Model B as data.")

_q(id="H01", category="hard",
   desc="Predicates asserted in the interior layer of a specific holon.",
   a="""SELECT DISTINCT ?p WHERE {
         oeq:q_hypertension_treatment holon:hasInteriorGraph ?g . GRAPH ?g { ?s ?p ?o } }""",
   b=None, b_unanswerable_reason=_NG_REASON, patterns_a=2)
_q(id="H02", category="hard",
   desc="All triples in the projection layer of a specific holon.",
   a="""SELECT ?s ?p ?o WHERE {
         oeq:q_hypertension_treatment holon:hasProjectionGraph ?g . GRAPH ?g { ?s ?p ?o } }""",
   b=None, b_unanswerable_reason=_NG_REASON, patterns_a=2)
_q(id="H03", category="hard",
   desc="Triple count per layer for a specific holon.",
   a="""SELECT ?layer (COUNT(*) AS ?n) WHERE {
         VALUES (?lp ?layer) {
           (holon:hasInteriorGraph "interior") (holon:hasBoundaryGraph "boundary")
           (holon:hasProjectionGraph "projection") (holon:hasContextGraph "context") }
         oeq:q_hypertension_treatment ?lp ?g . GRAPH ?g { ?s ?p ?o } }
         GROUP BY ?layer ORDER BY ?layer""",
   b=None, b_unanswerable_reason=_NG_REASON, patterns_a=2)
_q(id="H04", category="hard",
   desc="Which named graph (layer) asserts the questionText of a holon? (provenance-by-graph)",
   a="""SELECT ?g WHERE { GRAPH ?g { oeq:q_hypertension_treatment oe:questionText ?t } }""",
   b=None, b_unanswerable_reason=_NG_REASON, patterns_a=1)
_q(id="H05", category="hard",
   desc="Holons whose interior graph contains more than 8 triples.",
   a="""SELECT ?h (COUNT(*) AS ?n) WHERE {
         ?h holon:hasInteriorGraph ?g . GRAPH ?g { ?s ?p ?o } }
         GROUP BY ?h HAVING (COUNT(*) > 8)""",
   b=None, b_unanswerable_reason=_NG_REASON, patterns_a=2)
_q(id="H06", category="hard",
   desc="Total triple count grouped by layer across the whole corpus.",
   a="""SELECT ?layer (COUNT(*) AS ?n) WHERE {
         VALUES (?lp ?layer) {
           (holon:hasInteriorGraph "interior") (holon:hasBoundaryGraph "boundary")
           (holon:hasProjectionGraph "projection") (holon:hasContextGraph "context") }
         ?h ?lp ?g . GRAPH ?g { ?s ?p ?o } }
         GROUP BY ?layer ORDER BY ?layer""",
   b=None, b_unanswerable_reason=_NG_REASON, patterns_a=2)
_q(id="H07", category="hard",
   desc="Boundary-layer entry events reached via the holon's boundary graph.",
   a="""SELECT ?e ?entity WHERE {
         oeq:q_hypertension_treatment holon:hasBoundaryGraph ?g .
         GRAPH ?g { ?e a holon:EntityEntry ; holon:entity ?entity } }""",
   b=None, b_unanswerable_reason=_NG_REASON, patterns_a=3)
_q(id="H08", category="hard",
   desc="Subjects that appear in BOTH the interior and context layers of a holon (cross-layer join).",
   a="""SELECT DISTINCT ?s WHERE {
         oeq:q_hypertension_treatment holon:hasInteriorGraph ?gi ; holon:hasContextGraph ?gc .
         GRAPH ?gi { ?s ?p1 ?o1 } GRAPH ?gc { ?s ?p2 ?o2 } }""",
   b=None, b_unanswerable_reason=_NG_REASON, patterns_a=4)
_q(id="H09", category="hard",
   desc="The four layer-graph IRIs of a holon and the size of each.",
   a="""SELECT ?g (COUNT(*) AS ?n) WHERE {
         { oeq:q_hypertension_treatment holon:hasInteriorGraph ?g }
         UNION { oeq:q_hypertension_treatment holon:hasBoundaryGraph ?g }
         UNION { oeq:q_hypertension_treatment holon:hasProjectionGraph ?g }
         UNION { oeq:q_hypertension_treatment holon:hasContextGraph ?g }
         GRAPH ?g { ?s ?p ?o } } GROUP BY ?g""",
   b=None, b_unanswerable_reason=_NG_REASON, patterns_a=5)
_q(id="H10", category="hard",
   desc="Holons whose projection-layer summary confidence is below 0.5 (graph-scoped read).",
   a="""SELECT ?h ?sc WHERE {
         ?h a holon:ClinicalQuestionHolon ; holon:hasProjectionGraph ?g .
         GRAPH ?g { ?h holon:summaryConfidence ?sc } FILTER(?sc < 0.5) }""",
   b=None, b_unanswerable_reason=_NG_REASON, patterns_a=3)


def by_category() -> dict[str, int]:
    out: dict[str, int] = {}
    for q in QUERIES:
        out[q["category"]] = out.get(q["category"], 0) + 1
    return out


if __name__ == "__main__":
    print(f"Total queries: {len(QUERIES)}")
    for cat, n in by_category().items():
        print(f"  {cat:<8} {n}")
