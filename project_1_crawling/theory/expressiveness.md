# Expressiveness of the Holonic Model vs. Flat RDF — Formal Analysis

**Project 1 · RQ₁ / H₁.** *Does the RDF 1.2 holonic model provide measurably
higher expressiveness and queryability than flat RDF 1.1, without information
loss, and can this be measured formally?*

This document gives the formal definitions, the subsumption proof, and the
complexity analysis. Empirical values are produced by
[`src/benchmark.py`](../src/benchmark.py) and reported in
[`results/benchmark_summary.md`](../results/benchmark_summary.md).

---

## 1. Models

Let the source information be a finite set of clinical-evidence facts `F`. We
build two RDF encodings:

- **Model A (holonic, RDF 1.2).** A named-graph dataset
  `A = (G_def, {G_int^h, G_bnd^h, G_prj^h, G_ctx^h}_{h∈H})` where `H` is the set
  of holons and each holon contributes four layer graphs (Definition 1 of the
  framework). Edge-level metadata is attached by *materialised* RDF 1.2
  reification: a reifier node `r` typed `holon:EvidenceAssertion`, linked by
  `rdf:reifies` to a triple term `t` with `rdf:subject/predicate/object`, and
  carrying `holon:confidence`, `holon:evidenceLevel`, `holon:recordedOn`,
  `oe:cites`, `holon:inHolon`, `oe:effectiveness`.

- **Model B (flat, RDF 1.1).** A single default graph using *standard* RDF 1.1
  reification (`rdf:Statement` with `rdf:subject/predicate/object`) for the same
  metadata. There are **no named graphs**; the layer partition is not stored as
  data.

Both are produced from one normalisation by
[`src/rdf_transformer.py`](../src/rdf_transformer.py).

---

## 2. Expressiveness gain — definition

Following the framework (Definition 3) we define expressiveness operationally,
relative to a query benchmark `Q` and a fixed query language **L = SPARQL 1.1**:

> **Definition (answerability).** A query `q ∈ Q` is *answerable* over a model
> `M` iff there exists an `L`-expression of `q` over `M`'s vocabulary that, when
> evaluated, returns the intended (non-empty / `true`) answer **using only the
> data present in `M`** — i.e. without appealing to information that `M` does not
> store as RDF.

> **Definition (expressiveness gain).**
> `EG(A,B) = ( |Q_ans(A)| − |Q_ans(B)| ) / |Q|`.

The benchmark `Q` (file [`queries/benchmark_queries.py`](../queries/benchmark_queries.py))
has 50 queries: 15 simple, 15 medium (reification access), 10 complex
(temporal+provenance+confidence), 10 hard (holon-layer / named-graph identity).

**Measured result.** `|Q_ans(A)| = 50`, `|Q_ans(B)| = 40`, so
**`EG(A,B) = 20% ≥ 15%` → H₁ is supported.** All 10 unanswerable-in-B queries
are the *hard* class (H01–H10); on the 40 queries answerable in both, the result
sets are **identical** (`results/expressiveness.csv`), empirically witnessing the
information bijection of §3.

### 2.1 Why exactly the hard class separates the models

The flat model is information-preserving (Theorem 1, §3), so *no fact* is lost.
The separation is therefore **not** about information content but about what is
queryable *as data*:

- Queries H01–H10 range over the **layer/graph partition itself** — e.g. "list
  all triples in holon `h`'s projection layer", "count triples per layer",
  "which named graph asserts triple `τ`". In Model A the partition is first-class
  data (named graphs reachable via `holon:hasInteriorGraph` … + `GRAPH ?g`), so
  these are ordinary SPARQL queries.
- Model B does **not** record layer membership as a triple (that is precisely
  what makes it *flat*). A SPARQL query over `B` alone cannot recover the
  partition. The mapping `λ : predicate → layer` (§3) that *would* recover it is
  metadata external to the RDF, not queryable from within `B`.

Hence the 20% gain is a **named-graph / layer-provenance** expressiveness gain,
and we report it as such rather than overclaiming a difference in representable
information.

---

## 3. Information preservation — A and B are bijective

> **Theorem 1 (information preservation).** There is a bijection
> `β : 𝔽(A) ↔ 𝔽(B)` between the fact sets of the two models; consequently every
> query answerable over one model is answerable over the other *after a
> model-aware rewrite*. No information is lost in either direction.

**Proof (constructive).** Decompose each model into a canonical pair
`(CORE, ASRT)` (implemented in `benchmark._core_and_assertions`):

- `CORE` = all triples that are not reification plumbing and not the A-only
  named-graph pointers `holon:has{Interior,Boundary,Projection,Context}Graph`.
  These triples use stable entity/holon IRIs identical in both models, so
  `CORE(A) = CORE(B)`.
- `ASRT` = the set of canonical assertion records
  `⟨s,p,o,confidence,level,recordedOn,inHolon,effectiveness,cites⟩`. From Model A
  this is read off the reifier+triple-term; from Model B off the `rdf:Statement`.
  The two reification encodings are inter-translatable node-for-node, so
  `ASRT(A) = ASRT(B)`.

The layer partition of `A` is recovered in `B` by the total function
`λ : predicate → {interior, boundary, projection, context}` (table in
[`rdf_transformer.LAYER_OF_PREDICATE`](../src/rdf_transformer.py)); conversely
`A` is obtained from `B` by placing each triple `τ` into the named graph
`G_{λ(pred(τ))}^{holon(τ)}` and rewriting `rdf:Statement` to the RDF 1.2 reifier
form. Both directions are deterministic and mutually inverse, so `β` is a
bijection. ∎

**Measured result.** `CORE(A) = CORE(B)` and `ASRT(A) = ASRT(B)` hold exactly
(`results/info_preservation.json`: `bijection_holds = true`,
204 = 204 assertions, equal CORE sets).

**Corollary (honest reading of H₁).** Because `β` exists, the *strong* form of
H₁ ("the holonic model can answer queries the flat model fundamentally cannot")
is **false**: with an out-of-band rewrite the flat model could answer everything.
The defensible, measured claim is the *operational* one: under a fixed query
language and "data only" answerability, the holonic model answers **20% more**
benchmark queries, all in the layer/provenance class, and at no information cost.

---

## 4. Subsumption: holonic ⊒ flat

> **Proposition 1 (query subsumption).** For every flat query `q_B` there is a
> holonic query `q_A` with the same answer over corresponding data; i.e. the
> holonic model *subsumes* the flat model query-wise (`A ⊒ B`). The converse
> fails under the "data only" restriction (the hard class).

**Proof.** `B`'s default graph is contained in `A`'s **union (default) graph**
(`rdflib` `Dataset(default_union=True)`): every non-reification triple of `B` is
present unchanged in some named graph of `A` and hence in the union, and `B`'s
`rdf:Statement` metadata maps to `A`'s reifier metadata by `β`. Therefore the
identical SPARQL string (modulo the reification idiom) evaluated on `A`'s union
graph returns `q_B`'s answer. This is exactly what the benchmark shows: all 40
B-answerable queries are also A-answerable with identical results. The converse
fails because H01–H10 require `GRAPH`/layer data absent from `B` (§2.1). ∎

---

## 5. Complexity analysis

Let `n = |triples|`, `H` the number of holons, `b` the average holon size
(triples per holon), so `n ≈ |H|·b`.

**5.1 Reification access (medium/complex queries).** Reading the metadata of one
asserted edge costs:
- Model A: match `r rdf:reifies t`, then `t`'s three role triples, then the
  metadata — `Θ(1)` triple-pattern joins per edge (5 patterns, see
  `patterns_A`).
- Model B: match the `rdf:Statement`'s three role triples plus metadata —
  `Θ(1)` as well (5 patterns).
So per-edge metadata access is asymptotically equal; the models differ by a
constant idiom factor, not asymptotically. (Confirmed: `patterns_A ≈ patterns_B`
for M/C queries.)

**5.2 Layer-scoped queries (hard class).** With named graphs, "all triples in
layer `ℓ` of holon `h`" is a single graph lookup, `Θ(|G_ℓ^h|)`. Emulating it in a
flat store without layer data is impossible (§2.1); emulating it *if* layer were
materialised as a tag would cost an extra join per triple, `Θ(|G_ℓ^h|)` with a
larger constant. So the holonic model is never asymptotically worse and is
strictly more expressive here.

**5.3 Whole-model query cost.** A scan-style query is `Θ(n)` in both models.
Empirically (`results/expressiveness.csv`, `ms_A`/`ms_B`) the holonic dataset is
within a small constant factor of the flat graph; the named-graph index does not
change the asymptotics for these queries.

**5.4 Conformance checking (cross-reference to Framework Proposition 2).** SHACL
conformance over a holon hierarchy of depth `d` is `O(d · b · |S|)` for core
constraints and PSPACE-hard in general once `sh:sparql` constraints are present.
Our hand-off is validated by Project 2's engine; the full 216-holon corpus
conforms to the boundary-aware Set A with 0 violations (integration check,
`results/databook.md`).

---

## 6. Summary table

| Claim | Status | Evidence |
|-------|--------|----------|
| H₁: EG(A,B) ≥ 15% | **Supported (20%)** | `benchmark_summary.md` |
| Information preserved (bijection) | **Holds** | `info_preservation.json` |
| Holonic ⊒ flat (subsumption) | **Proven** (Prop. 1) | 40/40 identical shared results |
| Converse (flat ⊒ holonic) | **Fails** under data-only | hard class H01–H10 |
| Per-edge access asymptotically equal | **Yes** | §5.1, pattern counts |
| Gain localised to layer/provenance queries | **Yes** | category table |
