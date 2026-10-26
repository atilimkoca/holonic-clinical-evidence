# Project 3 — LLM Integration, Holon-Based Context Windowing & Hallucination Control

**Student C · BIL 930 Final Project · answers RQ₃:**

> Does **SHACL-guided** LLM generation with **holon-based context windowing**
> reduce the hallucination rate and the SHACL-conformance failure rate compared
> to standard (naive) GraphRAG?

**Result (this implementation): YES, on the two axes the holon design targets.**
On the 100-question test set, the holon-based system (A) vs naive GraphRAG (B):

| Metric | System A (holon) | System B (naive) | Test |
|--------|------------------|------------------|------|
| First-pass SHACL conformance | **100%** | 0% | McNemar p = 1.6×10⁻³⁰ |
| Converged conformance (k=3) | **100%** | 66% | McNemar p = 1.2×10⁻¹⁰ |
| Hallucination rate | **0.000** | 0.760 | Wilcoxon p = 2.1×10⁻¹⁹, d = 23.3 |
| Information coverage | 1.00 | 1.00 | — |
| Token efficiency (grounded/token) | **0.0006** | 0.0003 | Wilcoxon p = 3.9×10⁻¹⁸ |
| Mean context tokens | **131** | 507 | 3.9× smaller |

So **H₃ is supported** on every axis it targets. The holon boundary eliminates
hallucination (A = 0 vs B = 0.76, a huge effect) and the SHACL-guided prompt
makes generation conformant on the first pass (100% vs 0%). Even at **converged**
conformance the baseline does not catch up (66%): its over-fetched noise triples
inject *referential* (T2) violations that the SHACL-repair loop cannot fix, so
naive over-retrieval hurts both faithfulness **and** structural validity. System
A reaches the same coverage with **3.9× fewer context tokens**.

The complementary ten-question, specialty-stratified Ollama sensitivity run is
more nuanced. System A has higher converged conformance for Qwen3-8B
(100%/40%), Llama-3.1-8B (100%/60%), and Gemma3-4B (60%/0%), but hallucination
is unchanged at zero for Qwen/Gemma and higher for A with Llama
(0.467/0.100). Thus SHACL guidance improves structural validity more
consistently than semantic grounding; see
[`results/model_sensitivity/`](results/model_sensitivity/).

The controlled pipeline runs **offline and deterministically** on a built-in
mock LLM. The pluggable backend also supports OpenAI, Anthropic, and Ollama; the
reported sensitivity analysis uses the three local Ollama models above.

---

## What this sub-project delivers

| Assignment item | Where |
|---|---|
| §3.1 SHACL→Prompt `Transform(S)` + iterative-repair generation (k=3) | [src/shacl_to_prompt.py](src/shacl_to_prompt.py) · [src/llm_generator.py](src/llm_generator.py) → [prompts/templates/](prompts/templates/), [results/generated_rdf/](results/generated_rdf/) |
| §3.2 **Dual RAG**: holon-based (A) vs naive (B) | [src/graph_rag.py](src/graph_rag.py) |
| §3.3 Controlled experiment (conformance / hallucination / coverage) + stats | [src/run_experiment.py](src/run_experiment.py) · [src/evaluation.py](src/evaluation.py) → [results/summary.md](results/summary.md) |
| 2x2 ablation — Systems C/D isolate the retrieval and prompt factors | [src/run_ablation.py](src/run_ablation.py) · [src/run_ablation_sensitivity.py](src/run_ablation_sensitivity.py) → [results/ablation/summary.md](results/ablation/summary.md) |
| §3.3 Hallucination **annotation tool** (human ≥2 annotators) + κ + proxy | [src/annotate.py](src/annotate.py) → [data/questions/annotations/](data/questions/annotations/) |
| §3.4 Context Budget knapsack + NP-hardness + greedy + **scalability sweep** | [src/context_budget.py](src/context_budget.py) → [theory/context_budget_nphard.md](theory/context_budget_nphard.md), [results/performance/](results/performance/) |
| §3.5 Active inference: Bayesian update + KL surprise + `holon:terminates` | [src/holon_evolver.py](src/holon_evolver.py) → [results/active_inference/](results/active_inference/) |
| §3.6 Governance-aware LLM context (RQ₄) | [src/governance_context.py](src/governance_context.py) → [results/governance/](results/governance/) |
| Neo4J / NL query interface (API contract, Difficulty D) | [src/neo4j_query.py](src/neo4j_query.py) |
| 100-question gold test set from Project 1 holons | [src/dataset.py](src/dataset.py) → [data/questions/testset.json](data/questions/testset.json) |
| Pluggable LLM provider + offline cache | [src/llm_provider.py](src/llm_provider.py) |
| Theory: Transform correctness + convergence | [theory/transform_correctness.md](theory/transform_correctness.md) |
| Theory: hallucination taxonomy (Type A/B/C) | [theory/hallucination_taxonomy.md](theory/hallucination_taxonomy.md) |
| Reproducible analysis notebook | [results/analysis.ipynb](results/analysis.ipynb) |
| Tests | [tests/test_project3.py](tests/test_project3.py) |

**Difficulty layers owned:** **E** (LLM hallucination detection — the core
experiment), **B** (temporal event modelling via `holon_evolver`), and **F**
(multi-model comparison). The sensitivity analysis was executed locally with
Qwen3-8B, Llama-3.1-8B, and Gemma3-4B through Ollama.

---

## Quick start

```bash
# from the repo root; uses the shared .venv (Python 3.9)
python -m pip install -r project_3_llm/requirements.txt

cd project_3_llm/src
python dataset.py             # build the 100-question test set (seed 42)
python run_experiment.py      # Deney 1/2/3 -> ../results/{summary.md,accuracy,...}
python run_ablation.py        # 2x2 ablation A/C/D/B (retrieval x prompt) -> ../results/ablation/
python run_model_sensitivity.py  # three local models -> ../results/model_sensitivity/
python run_ablation_sensitivity.py  # real-model 2x2 ablation -> ../results/ablation_sensitivity/
python context_budget.py      # knapsack + latency + scalability sweep
python holon_evolver.py       # active inference + holon:terminates demo
python governance_context.py  # RQ4 governance-aware context
python annotate.py --mode simulate   # annotated dataset + Cohen's kappa

# tests
cd .. && python -m pytest tests -q
```

### Using a real LLM (optional)

```bash
export P3_LLM_PROVIDER=openai      # or anthropic | ollama
export OPENAI_API_KEY=sk-...       # (ANTHROPIC_API_KEY for Claude; none for ollama)
python src/run_experiment.py       # responses are cached under data/llm_cache/ for replay
```

Everything is cached after the first call, so a real run becomes replayable and
deterministic — the same philosophy as Project 1's PubMed cache.

---

## The two systems (§3.2)

Both share the same LLM, the same 100 questions, and the same metric suite; only
the retrieval/prompting design differs.

- **System A — Holon-Based GraphRAG.** Retrieval is bounded to the relevant
  holon; context is the **projection layer + confidence-weighted interior
  facts** of that holon; the SHACL shape is prepended as a prompt prefix
  (SHACL-guided). The holon boundary excludes cross-holon facts ⇒ no Type-A
  hallucination, and the context stays small (~132 tokens, flat as the corpus
  grows — see [results/figures/scalability.png](results/figures/scalability.png)).
- **System B — Naive GraphRAG.** TF-IDF retrieval over **all** triples (top-k
  holons unioned), raw-triple dump, no SHACL, no confidence filter. It over-fetches
  loosely related facts (~1 ungrounded fact/question) and misses the holon
  scaffold on the first pass.

## Hallucination taxonomy (Type A/B/C)

| Code | Class | Decision rule |
|------|-------|---------------|
| **A** | ungrounded but factual | pair ∉ this question's grounded facts, ∈ corpus |
| **B** | ungrounded & incorrect | pair ∉ the whole corpus (fabricated) |
| **C** | contradictory | pair attested but emitted verdict negates the grounded one |

Grounding oracle = Project 1's 216-holon corpus (each fact traceable to a PubMed
source). Formal definitions in [theory/hallucination_taxonomy.md](theory/hallucination_taxonomy.md).

---

## Threats to Validity (read before grading)

1. **Default LLM is a deterministic mock.** To keep the project offline,
   secret-free and reproducible (Projects 1 & 2's philosophy; the assignment
   explicitly permits LLM-emulated pipelines), the default provider is a
   *prompt-driven simulator*. It is **not** a substitute for a real LLM's
   generative ability; it faithfully propagates the **information content** of
   each system's prompt (System A ships SHACL `required_fields` + a holon
   template + grounded-only facts; System B ships an unconstrained naive prompt +
   noisier facts), so the A-vs-B comparison reflects the *design under test*, not
   a hard-coded verdict. Real-LLM mode (`P3_LLM_PROVIDER`) replaces it and the
   metrics/stat tests are unchanged. Because the mock is grounded-by-construction
   it emits only **Type A** hallucinations for System B; the classifier handles
   B/C and is exercised by the unit tests — genuine B/C appear only with a real LLM.
2. **Conformance is driven by the design, not magic.** System A conforms on the
   first pass because it is *given* the SHACL template; System B fails first
   (missing the holon scaffold) and only partially recovers (66%) because its
   over-fetched noise triples carry referential (T2) violations the repair loop
   cannot fix. With a different prompt/retriever these gaps would shift; we
   report first-pass *and* converged so the mechanism is transparent.
3. **Lexical, not neural, retrieval.** The retriever is deterministic TF-IDF
   (no heavy deps). A neural encoder (`sentence-transformers`) is supported but
   off by default; rankings — and thus System B's noise set — would shift with a
   different encoder.
4. **Grounding oracle is recall-limited.** A drug–disease link absent from
   Project 1's crawl is scored Type B even if true in the wider literature.
5. **Inter-annotator agreement is proxy-based by default** (κ = 0.78 over 110
   generated assertions, rule-based labels vs a perturbed second automated pass). It measures the *stability* of the
   grounding rule, not human consensus; `annotate.py --mode interactive` exists
   so a grader can produce the authentic two-annotator κ on a sample.
6. **Scalability ≥ 216 holons is synthetic.** The 500/1000/5000-holon points
   replicate the 216 real holons (Project 1's crawl size); they measure system
   *scaling behaviour*, not new evidence.
7. **RDF 1.2 materialisation.** Like Projects 1 & 2, reification is materialised
   (`holon:EvidenceAssertion` + `rdf:reifies` + triple term) because rdflib/
   pyshacl do not parse Turtle-1.2 `{| |}`; generated output uses the same
   convention, so it validates against Project 2's shapes unchanged.

---

## Repository map

```
project_3_llm/
├── src/
│   ├── namespaces.py          # shared prefixes (aligned with Projects 1/2)
│   ├── llm_provider.py        # pluggable mock/OpenAI/Anthropic/Ollama + cache
│   ├── shacl_to_prompt.py     # Transform(S): SHACL shape -> prompt template
│   ├── llm_generator.py       # SHACL-guided generation + k=3 repair loop
│   ├── dataset.py             # Project-1 corpus -> 100-question gold test set
│   ├── graph_rag.py           # dual RAG: holon-based (A) vs naive (B)
│   ├── context_budget.py      # knapsack selection + scalability sweep
│   ├── evaluation.py          # Type A/B/C classifier, coverage, kappa
│   ├── annotate.py            # human/proxy annotation tool + inter-annotator kappa
│   ├── holon_evolver.py       # active inference + holon:terminates
│   ├── governance_context.py  # centralized/federated/autonomous (RQ4)
│   ├── neo4j_query.py         # natural_language_query() (SPARQL/Cypher)
│   └── run_experiment.py      # Deney 1/2/3 + statistics (the main entry point)
├── prompts/templates/         # generated MadLibs prompt templates
├── data/questions/            # testset.json + annotations/
├── data/llm_cache/            # committed offline response cache
├── results/                   # summary.md, accuracy/ hallucination/ performance/
│   ├── generated_rdf/         # LLM-produced .ttl (validated by Project 2)
│   ├── active_inference/  governance/  figures/  analysis.ipynb
├── theory/                    # transform_correctness, context_budget_nphard,
│                              # hallucination_taxonomy
├── tests/test_project3.py
└── requirements.txt
```

## Integration (group phase)

Per [shared/interfaces/api_contracts.md](../shared/interfaces/api_contracts.md),
Project 3 exposes `natural_language_query(...)`, writes LLM output to
`results/generated_rdf/` (validated by Project 2's `validate_graph`), and provides
the governance-aware context strategies for the joint RQ₄ end-to-end experiment.
The end-to-end demo wiring itself is the shared integration phase (as in Project 2).
