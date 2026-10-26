# Holonic Knowledge Representation for Clinical Evidence — code and data

This repository contains the code, data and generated artifacts for the article

> D. Kılınç, O. Er, O. Bursa, M. Uçar, Ö. A. Koca, E. Turan, K. Kıvırcık.
> *Holonic Knowledge Representation for Clinical Evidence: Boundary-Aware Validation and
> Hallucination Control in LLM-Augmented Knowledge Graphs.* Submitted to *Data & Knowledge
> Engineering*, 2026.

The ontology modules (`holon:`, `oe:`, `medical`) are published separately at
<https://atilimkoca.github.io/syz-ontology/>.

## Contents

| Folder | What it contains | Article |
|---|---|---|
| `project_1_crawling/` | PubMed retrieval through NCBI E-utilities (cached), entity and relation extraction, holonic (Model A) and flat (Model B) RDF exports, the 50-query SPARQL benchmark, holon-level graph analysis, data-layer governance, Cypher export | RQ1, RQ4 (data layer) |
| `project_2_semantic/` | Holon ontology, SHACL Set A (boundary-aware), Set B (assertion-scoped) and Set C (context-aware flat control), the 100-holon inconsistency corpus, validation reports, statistics, validation-layer governance | RQ2, RQ4 (validation layer) |
| `project_3_llm/` | SHACL-guided holon-bounded GraphRAG, the deterministic provider, cached real-model completions, the 2×2 ablation, the hallucination classifier, context-budget optimisation, LLM-context governance, temporal evidence updating | RQ3, RQ4 (LLM-context layer) |
| `integration/` | End-to-end smoke pipeline and integration tests | Integration results |
| `shared/` | Shared ontology files, API contracts, 20-holon integration test set | — |
| `paper_artifacts/` | The files reproduced in the article's appendices (holon examples, SHACL shapes and reports, prompts, generated outputs, queries, proof notes) | Appendices |

The README files inside the sub-project folders were written during the original project and
summarise the first results. The article is the authoritative description and interpretation;
in particular, its Set C control qualifies the RQ2 result.

## Requirements

Python 3.10 or later (tested with Python 3.11). Install the dependencies of all sub-projects:

```bash
pip install -r project_1_crawling/requirements.txt \
            -r project_2_semantic/requirements.txt \
            -r project_3_llm/requirements.txt
```

No API key, network access, Neo4J server or GPU is needed for the default pipeline: PubMed
responses and real-model completions are cached, and the primary generation experiment uses a
deterministic provider.

## Running the tests

From the repository root:

```bash
python -m pytest project_1_crawling/tests -q
(cd project_2_semantic && python -m pytest -q)
(cd project_3_llm && python -m pytest -q)
python -m pytest integration/src/integration_tests.py -q
python integration/src/end_to_end_pipeline.py --sample-size 20
```

The Project 1 tests rerun the representation pipeline and rewrite files under
`project_1_crawling/data/` and `project_1_crawling/results/`. With the current code, the
aggregate-confidence value of six holons differs from the archived files in the second decimal
place; the archived files are the ones used in the article.

To replay the PubMed crawl from the bundled cache without network access:

```bash
python -m project_1_crawling.src.crawler --offline --refresh
```

Set your own e-mail address in `project_1_crawling/config/crawl_config.yaml` before a live crawl,
as NCBI requests.

## Data notes

- `project_1_crawling/data/raw/` contains PubMed records (titles, abstracts and bibliographic
  metadata) retrieved through NCBI E-utilities, and the derived RDF files quote parts of them.
  They are included only so that the results can be reproduced. Copyright in abstracts remains
  with their original publishers; see the NLM terms and conditions for PubMed data.
- `project_3_llm/data/llm_cache/` contains the recorded completions of the locally run models
  (Qwen3-8B, Llama-3.1-8B, Gemma3-4B via Ollama, temperature 0), so these runs replay exactly.
- The extracted clinical relations are research artifacts, not curated therapeutic
  recommendations, and must not be used for clinical decisions.

## Licence

- Code: MIT Licence (`LICENSE`).
- Data, RDF exports, SHACL shapes and other generated artifacts created for this work:
  Creative Commons Attribution 4.0 International (`LICENSE-DATA`).
- Third-party content, in particular PubMed titles and abstracts, remains under the terms of its
  respective rights holders.
