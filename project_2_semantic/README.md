# Project 2 — Holonic Semantic Layer, Boundary-Aware SHACL & Inconsistency Detection

**Student B** · BIL 930 Final Project · answers **RQ₂**:

> Do holon **boundary shapes** defined with SHACL 1.2 detect *statistically
> significantly* more semantic inconsistencies than **flat** SHACL validation?

**Result (this implementation): YES.** Boundary-aware validation detects
**100%** of injected inconsistencies vs **52%** for flat SHACL; McNemar's exact
test gives **p = 1.19 × 10⁻⁷**, so H₀ is rejected. The advantage is entirely in
the T4–T6 classes that require holon context (see below).

---

## What this sub-project delivers

| Assignment item | Where |
|---|---|
| 2.1 Holon ontology + worked examples | [ontology/holon_ontology.ttl](ontology/holon_ontology.ttl) (extends `shared/ontology`) + 3 full four-layer holons in [examples/](examples/) (Disease / EvidenceChain / ClinicalQuestion) |
| 2.2 Dual SHACL sets (boundary-aware **Set A** + flat **Set B**) | [shacl/shapes/boundary_aware/](shacl/shapes/boundary_aware/) · [shacl/shapes/flat/](shacl/shapes/flat/) |
| 2.3 100-holon inconsistency corpus (T1–T6, gold-labelled) | [src/corpus_generator.py](src/corpus_generator.py) → `corpus/holons/` |
| 2.4 Comparative experiment + McNemar's test | [src/run_experiment.py](src/run_experiment.py) → `results/` |
| 2.5 Expressiveness limits, **Proposition 4**, decidability | [theory/expressiveness_and_decidability.md](theory/expressiveness_and_decidability.md) + [theory/scoping_demo.py](theory/scoping_demo.py) (runnable Theorem 2 witness) |
| 2.6 OWL→SHACL conversion + loss analysis | [src/owl_to_shacl.py](src/owl_to_shacl.py) on **real MeSH** → [theory/mesh_to_shacl_loss.md](theory/mesh_to_shacl_loss.md) (98%, shapes validated on 5 real descriptors) + synthetic stress-test → [theory/owl_to_shacl_loss.md](theory/owl_to_shacl_loss.md) (64%) |
| 2.7 Governance-dependent validation (RQ₄) | [src/governance_validation.py](src/governance_validation.py) → [theory/governance_validation.md](theory/governance_validation.md) |
| Report figures | [src/make_figures.py](src/make_figures.py) → `results/figures/` |
| Validation engine (API contract) | [src/shacl_validator.py](src/shacl_validator.py) |
| Tests | [tests/test_validation.py](tests/test_validation.py) |

**Status:** all §2.1–§2.7 deliverables are implemented and runnable. The group
phase integration demo and final report are handled at repository level
(`integration/`, `report/final_report.pdf`). The RQ2 corpus remains a controlled
synthetic benchmark; Project 1 data is exercised separately by the integration
pipeline.

---

## Quick start

```bash
# from repository root
python3 -m pip install -r project_2_semantic/requirements.txt

python3 project_2_semantic/src/corpus_generator.py      # generate corpus/holons/ (seed=42)
python3 project_2_semantic/src/run_experiment.py        # writes results/{metrics,outcomes,summary.md,contingency}.csv|md

# extended RQ2 with the reviewer-requested Set C (flat RDF + context-aware SPARQL SHACL)
python3 project_2_semantic/src/flatten_corpus.py        # corpus/holons_flat/ (flat export, same manifest)
python3 project_2_semantic/src/run_three_sets.py        # writes results/three_sets/{metrics,outcomes,summary.md,contingency}.csv|md

# governance validation incl. the centralized (C1) 500/1000-holon benchmark
python3 project_2_semantic/src/governance_validation.py --sizes 50,100,200,500,1000 --c1-max 1000

# tests
python3 -m pytest project_2_semantic/tests -q
```

---

## The inconsistency taxonomy (T1–T6)

| Code | Class | Example injected defect | Caught by |
|------|-------|-------------------------|-----------|
| **T1** | Structural | mandatory `holon:confidence` removed | A & B |
| **T2** | Referential | citation points to an undeclared source | A & B |
| **T3** | Temporal | evidence recorded *before* its source was published | A & B |
| **T4** | Semantic | `"effective"` claim admitted *below* the holon's quality threshold | **A only in this baseline** |
| **T5** | Cross-holon | two holons assert opposite effectiveness for the same drug–disease | **A only in this baseline** |
| **T6** | Projection | projected aggregate confidence diverges from interior evidence | **A only in this baseline** |

T4–T6 are missed by Set B because this flat baseline deliberately removes the
holon context needed by those checks: the **boundary** quality threshold (T4),
holon **membership** `holon:inHolon` (T5), and the **projection layer** vs
interior (T6). This is the controlled variable of the experiment. It is not a
claim that any flat RDF graph with equivalent boundary/layer data and custom
SPARQL could never emulate the checks; that stronger claim is explicitly
qualified in [theory/expressiveness_and_decidability.md](theory/expressiveness_and_decidability.md).

## Headline results (`results/summary.md`)

| Type | Set A recall | Set B recall |
|------|------|------|
| T1–T3 | 1.00 | 1.00 |
| T4–T6 | 1.00 | 0.00 |
| **ALL** | **1.00** | **0.52** |

McNemar contingency (paired correctness over 100 holons): discordant pairs
A-right/B-wrong = **24**, A-wrong/B-right = **0** → statistic 0, **p = 1.19e-07**.
This supports **H₂** (≥25% more inconsistencies detected): flat 52% → boundary
100%.

---

## Threats to Validity (important — read before grading)

1. **RDF 1.2 tooling.** `rdflib 7.6` / `pyshacl 0.31` do **not** parse the
   Turtle 1.2 annotation syntax (`:s :p :o ~ :r {| … |}`) nor execute
   `sh:reifierShape`. We therefore **materialise** every RDF 1.2 reification as
   an explicit reifier node typed `holon:EvidenceAssertion`, linked by
   `rdf:reifies` to a triple-term node (`rdf:subject/predicate/object`). The
   shapes keep the canonical `sh:reifierShape` linkage *for documentation /
   assignment fidelity*, but the **runnable** enforcement targets reifier nodes
	   via `sh:targetClass holon:EvidenceAssertion` **and**
	   `sh:targetSubjectsOf rdf:reifies` (the pattern from Cagle, *“When Predicates
	   Lie”*). Both select exactly the reifier nodes, so the semantics match; only
	   the surface syntax differs. We report this as a tooling threat rather than
	   hiding it.

2. **No rdfs inference.** Validation runs with `inference="none"` on purpose: a
   `rdfs:domain` axiom would re-type any holon carrying a chain-only property as
   an `EvidenceChainHolon` and create false positives. `sh:class` still honours
   `rdfs:subClassOf` from the ontology graph without inference.

3. **Synthetic corpus.** The corpus is generated, not crawled — defects are
   injected with a fixed seed (reproducible) but may not match the natural
   distribution of real OpenEvidence errors. Set A's perfect score reflects a
	   *controlled* setting; real data will be noisier. Project 1's crawled data is
	   exercised in the repository-level integration pipeline, while this RQ2
	   benchmark stays fixed so Set A and Set B are compared on identical labelled
	   defects.

4. **Construct validity.** Because we *designed* T4–T6 to need holon context,
	   the experiment shows boundary-awareness is *sufficient* to catch the
	   non-local classes under the stated flat baseline. It does **not** claim every
	   real-world semantic error has this shape, nor that a flat graph enriched with
	   equivalent boundary metadata and custom SPARQL could never emulate the same
	   checks.

---

## Mapping to the SHACL features required by §2.2

`sh:targetClass`, `sh:path`, `sh:datatype`/`sh:class`, `sh:minCount`/`maxCount`,
`sh:pattern`/`sh:in`, `sh:node` (×7 in `03_boundary_shapes.ttl`), `sh:or`/`sh:xone`
(×5), `sh:sparql` (×6 Set A, ×6 Set B), `sh:deactivated` (Set B boundary-only
name-parity declarations), `sh:reifierShape` (**×6** across
`01`/`02`/`05`, ≥5 as required), `sh:resultAnnotation` (in `02_reifier_shapes.ttl`),
`sh:severity` (Violation/Warning/Info throughout).

**All 12 mandatory §2.2 shape names are present by exact name.** Set A contains
the executable boundary-aware versions. Set B uses the same exact names for the
flat executable counterparts where the check is local, and declares the
boundary-only names as `sh:deactivated true` so the flat baseline remains a real
baseline rather than a disguised boundary-aware validator.

**Other §2 deliverables now produced:** Turtle validation reports per gold type
(`shacl/validation_reports/`), 95% bootstrap confidence intervals on recall
(`results/summary.md`), and corpus annotation with type + layer + location +
severity (`corpus/holons/manifest.csv`).
