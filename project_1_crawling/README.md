# Project 1 — Holonic Data Modeling, Expressiveness & Graph Topology

**Student A · BIL 930 Final Project · answers RQ₁**

> Does an RDF 1.2 *holonic* data model provide measurably higher expressiveness
> and queryability than flat RDF 1.1, **without information loss**, and can this
> be shown formally?

**Result (this implementation):**
- **Information is preserved** — an A↔B bijection holds exactly (CORE 11329=11329, 204=204 reified assertions).
- **Expressiveness gain EG(A,B) = 20% ≥ 15% → H₁ SUPPORTED**, concentrated entirely in holon-layer / named-graph queries; on the 40 shared queries the two models return **identical** results.
- The whole 216-holon hand-off **validates against Student B's boundary-aware SHACL (Set A) with 0 violations** — the cross-project integration works.

The data is **real**: 864 PubMed abstracts crawled from the NCBI E-utilities API
across 72 diseases / 10 specialties, cached for offline reproducibility.

---

## What this sub-project delivers

| Assignment item | Where |
|---|---|
| §1.1 Crawling + entity extraction (≥200 Q&A, ethics) | [src/crawler.py](src/crawler.py) · [src/pubmed_client.py](src/pubmed_client.py) · [src/entity_extractor.py](src/entity_extractor.py) → `data/raw/`, `data/processed/` |
| §1.2 **Dual model**: holonic RDF 1.2 (Model A) + flat RDF 1.1 (Model B), info-preserving bijection | [src/rdf_transformer.py](src/rdf_transformer.py) → `data/rdf/holonic/`, `data/rdf/flat/` |
| §1.3 **50-query SPARQL benchmark** + expressiveness + bijection | [queries/benchmark_queries.py](queries/benchmark_queries.py) · [src/benchmark.py](src/benchmark.py) → `results/expressiveness.csv`, `results/benchmark_summary.md` |
| §1.4 **Holon-level graph topology**, community detection, homomorphism, subsumption | [src/graph_analysis.py](src/graph_analysis.py) → `results/graph_metrics.json`, `results/graph_analysis.md` |
| §1.5 Neo4J import + Cypher benchmark (Difficulty D) | [src/neo4j_loader.py](src/neo4j_loader.py) → `results/neo4j/` (live DB optional) |
| §1.6 **DataBook** provenance pipeline + per-step SHACL report | [src/databook_pipeline.py](src/databook_pipeline.py) → `results/databook_provenance.json`, `results/databook.md` |
| §1.7 **Governance-aware architecture** (centralized/federated/autonomous, RQ₄) | [src/governance.py](src/governance.py) → `results/governance.json`, `results/governance.md` |
| Formal theory (expressiveness, bijection, homomorphism, complexity) | [theory/](theory/) |
| Tests | [tests/test_pipeline.py](tests/test_pipeline.py) |

---

## Quick start

```bash
# from the Final_Project/ repo root
python -m pip install -r project_1_crawling/requirements.txt

# rebuild EVERYTHING from the cached crawl (no network needed):
python -m project_1_crawling.src.databook_pipeline --offline

# or refresh the crawl from PubMed first (needs internet), then rebuild:
python -m project_1_crawling.src.crawler            # re-crawl (cached)
python -m project_1_crawling.src.databook_pipeline

# run the tests
python -m pytest project_1_crawling/tests -q
```

Individual stages can also be run on their own, e.g.
`python -m project_1_crawling.src.benchmark` or
`python -m project_1_crawling.src.graph_analysis`.

---

## The two models (§1.2)

Both encode the **same** clinical evidence; they differ only in *structure*.

**Model A — Holonic (RDF 1.2), `data/rdf/holonic/model_a.trig`.**
A named-graph dataset: each holon has four layer graphs (interior / boundary /
projection / context). Edge metadata uses the **materialised RDF 1.2 reification**
pattern — the *same convention Project 2 uses* — so the data is interoperable:

```turtle
# interior graph of a clinical-question holon
oedrug:lisinopril oe:treats oed:hypertension .
oeevt:ev_q_hypertension_treatment a holon:EvidenceAssertion ;
    rdf:reifies oeevt:ev_q_hypertension_treatment-tt ;
    holon:confidence 0.95 ; holon:evidenceLevel "Level-1A" ;
    holon:assessedBy oeq:openevidence_ai ; holon:recordedOn "2025-06-01"^^xsd:date ;
    oe:cites oesrc:34567890 ; holon:inHolon oeq:q_hypertension_treatment ;
    oe:effectiveness "effective" .
oeevt:ev_..._treatment-tt rdf:subject oedrug:lisinopril ;
    rdf:predicate oe:treats ; rdf:object oed:hypertension .
```

**Model B — Flat (RDF 1.1, baseline), `data/rdf/flat/model_b.ttl`.**
A single default graph, **no named graphs**, standard `rdf:Statement` reification.
It carries every fact A does (so the bijection holds) but does **not** record the
layer partition as data — which is exactly the queryability the benchmark
measures.

The conceptual target of Model A is the Turtle 1.2 annotation syntax
(`:s :p :o ~ :r {| … |}`); we **materialise** it because `rdflib`/`pyshacl`
cannot yet parse that surface form (see *Threats to validity*).

---

## Headline results

| Metric | Value | Source |
|--------|-------|--------|
| Clinical-question holons | **216** | `data/processed/extract_stats.json` |
| Unique entities | **4 825** | same |
| Real PubMed articles crawled | **864** (0 synthetic) | `data/raw/crawl_summary.json` |
| Model A triples / named graphs | **14 573 / 866** | `results/model_stats.json` |
| Reification ratio | **0.573** (≥0.50 required) | same |
| **Expressiveness gain EG(A,B)** | **20%** (A 50/50, B 40/50) | `results/benchmark_summary.md` |
| Shared queries with identical results | **40 / 40** | `results/expressiveness.csv` |
| **Information-preservation bijection** | **holds** | `results/info_preservation.json` |
| Community modularity / purity / NMI vs specialty | **0.92 / 0.83 / 0.68** | `results/graph_metrics.json` |
| Cross-level Spearman(betweenness, confidence) | **0.03 (p=0.62)** — no correlation | same |
| Project 2 Set A validation of full corpus | **0 violations** | `results/databook.md` |

---

## Integration — how Student C (Project 3) consumes this

Per [shared/interfaces/api_contracts.md](../shared/interfaces/api_contracts.md):

- **RDF for the semantic/LLM layers** is in `data/rdf/holonic/`:
  - `clinical_questions/*.ttl` — one Turtle file per holon (materialised; parses
    in a single `rdflib.Graph`, validated by Project 2);
  - `entities/{diseases,drugs,sources,symptoms}.ttl`, `relationships.ttl`.
- **Whole-corpus** convenience graphs: `all_holonic.ttl` (Model A merged) and
  `flat/model_b.ttl` (baseline).
- **Neo4J**: `results/neo4j/import_holonic.cypher` builds the property-graph
  projection; set `NEO4J_URI/USER/PASS` and run `neo4j_loader` for the live
  Cypher comparison. (`bolt://localhost:7687`, database `openevidence` per the
  contract.)
- The data is already verified to **conform to Project 2's SHACL shapes**, so the
  semantic layer needs no changes to ingest it.

---

## Threats to validity (read before grading)

1. **Data source.** OpenEvidence.com is login-gated and prohibits scraping, so we
   crawl the public **PubMed E-utilities** API instead (explicitly permitted by
   the assignment). Holons are reconstructed from primary-literature abstracts
   rather than OpenEvidence's synthesised answers — a *construct-validity* threat.
2. **RDF 1.2 tooling.** `rdflib 7.4` / `pyshacl 0.31` do not parse the Turtle 1.2
   annotation syntax nor execute `sh:reifierShape`, so RDF 1.2 reification is
   **materialised** (reifier node + `rdf:reifies` + triple term). This matches
   Project 2's choice, so the two layers interoperate; only the surface syntax
   differs from the standard.
3. **Synthetic fabrication dates.** Drug approval dates and disease
   first-described dates are deterministically synthesised (seed 42) because
   PubMed does not expose them per entity; they are internally consistent (drug
   approval always after disease description) but not authoritative.
4. **Expressiveness reading.** Because the A↔B bijection holds, the *strong* form
   of H₁ is false — with an out-of-band rewrite the flat model could answer
   everything. The measured 20% gain is the *operational* "data-only,
   fixed-query-language" gain, localised to named-graph/layer queries, and is
   reported as such (see [theory/expressiveness.md](theory/expressiveness.md)).
5. **Scale.** 216 holons / 14.5k triples; the scalability curve subsamples to
   50/100/150/216. The assignment's 1000/5000-holon points would need a larger
   crawl (the pipeline supports it by extending `config/crawl_config.yaml`).

---

## Repository map

```
project_1_crawling/
├── config/crawl_config.yaml      # diseases, drugs, query templates, crawl settings
├── src/
│   ├── pubmed_client.py          # cached, rate-limited E-utilities client
│   ├── crawler.py                # per-disease article pools (offline-safe)
│   ├── entity_extractor.py       # raw -> normalised entities + holons
│   ├── rdf_transformer.py        # Model A (holonic) + Model B (flat) + Project 2 hand-off
│   ├── benchmark.py              # 50-query expressiveness + bijection check
│   ├── graph_analysis.py         # holon topology, communities, homomorphism
│   ├── governance.py             # centralized/federated/autonomous trade-offs
│   ├── neo4j_loader.py           # Cypher import + benchmark (live DB optional)
│   ├── databook_pipeline.py      # provenance pipeline / full runner
│   └── run_all.py                # convenience entry point
├── queries/benchmark_queries.py  # the 50 SPARQL queries (+ Cypher)
├── theory/                       # expressiveness, info-preservation, homomorphism, complexity
├── data/  (raw/ processed/ rdf/) # crawled cache + processed JSON + RDF outputs
├── results/                      # csv/json/md metrics + figures/
├── tests/test_pipeline.py
└── requirements.txt
```
