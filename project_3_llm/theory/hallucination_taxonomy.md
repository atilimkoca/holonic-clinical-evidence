# §3.3 — Hallucination Taxonomy (Type A / B / C): Formal Definitions & Grounding

**Project 3 (Student C) — formal companion to
[`../src/evaluation.py`](../src/evaluation.py) and
[`../src/annotate.py`](../src/annotate.py).** Defines the hallucination classes,
the grounding procedure that decides them, and the inter-annotator-agreement
protocol.

---

## 1. Grounding model

Fix a question holon `q` with cited sources `Src(q)` and grounded fact set

```
G(q) = { (drug, disease, eff) : the holon's interior reifies drug oe:treats
         disease with effectiveness eff, citing s ∈ Src(q) }.
```

Let `K = ⋃_h G(h)` be the **corpus knowledge base** — every grounded fact across
all 216 Project-1 holons (each itself traceable to a PubMed source in
`project_1_crawling/data/raw/pubmed_cache/`). For a pair `p = (drug, disease)`
write `K(p)` for the multiset of effectiveness verdicts the corpus records for
`p`, and `consensus(p) = argmax` of that multiset.

A model output `O` asserts a set `A(O)` of `(drug, disease, eff?)` facts
(`extract_asserted` reads them from the generated RDF: reified
`holon:EvidenceAssertion` nodes give effectiveness; bare `oe:treats` triples are
unsigned over-generation).

## 2. The taxonomy

For an asserted fact `a = (p, e) ∈ A(O)` against question `q`:

> **Definition 1 (Grounded).** `a` is *grounded* iff `p ∈ pairs(G(q))` and
> (`e` unset or `e` equals the holon's verdict). Grounded facts are faithful:
> the holon's own cited evidence supports them.

> **Definition 2 (Type A — ungrounded but factual).** `p ∉ pairs(G(q))` but
> `p ∈ pairs(K)`: the link is real (some corpus holon, hence some PubMed source,
> asserts it) yet it is **not** part of what `q` asked or cited. This is the
> classic RAG failure mode — pulling in true-but-off-topic facts.

> **Definition 3 (Type B — ungrounded and incorrect).** `p ∉ pairs(K)`: neither
> the question nor any corpus source attests the link. The model fabricated a
> drug–disease relation (or an entity). This is the most dangerous class.

> **Definition 4 (Type C — contradictory).** `p` is attested (in `G(q)` or `K`)
> but the emitted verdict `e` is the negation of the grounded/consensus verdict
> (`e = ¬verdict`). The model inverts a real finding.

These map exactly onto the assignment's "ungrounded but factual / ungrounded and
incorrect / contradictory" (Tip A/B/C). `classify_fact` implements Definitions
1–4; the precedence is grounded → C (contradiction) → A → B.

> **Definition 5 (Hallucination rate).**
> `HR(O, q) = (|A| + |B| + |C|) / |A(O)|`, the fraction of asserted facts that
> are not grounded. **Information coverage** is `|pairs(A(O)) ∩ pairs(G(q))| /
> |pairs(G(q))|`; **precision@k** is the grounded fraction of the first `k`
> asserted facts (reified, faithful content emitted before bare over-generation).

## 3. Why holon-based (System A) should hallucinate less

System A's context is the holon's **projection layer** plus **confidence-filtered
interior** facts, bounded by the holon boundary; it therefore can only assert
`p ∈ pairs(G(q))` (grounded) — `A(O_A) ⊆ G(q)` ⇒ `HR(O_A) = 0` in the limit.
System B retrieves the top-`k` *similar* holons and dumps their raw triples, so
its candidate set is `⋃_{h∈topk} pairs(G(h)) ⊇ pairs(G(q))`; the extra pairs are
Type A by construction (real corpus facts, wrong question). Hence

```
HR(O_B) ≥ HR(O_A)  with strict inequality whenever naive retrieval surfaces a
neighbouring holon's fact — which the measured ~1 noise fact/question confirms.
```

Type B/C require *generation* beyond the retrieved set; the default deterministic
mock is grounded-by-construction and so emits only Type A for System B (its
`classify_fact` still detects B/C, exercised by the unit tests and by the
`evaluation.py` demo). A **real** LLM (`P3_LLM_PROVIDER=openai|anthropic|ollama`)
is what surfaces genuine Type B/C, and the classifier scores those unchanged.

## 4. Gold standard & inter-annotator agreement

The assignment requires a human gold standard with ≥ 2 annotators and a reported
agreement. `annotate.py` provides:

1. **Human path** (`--mode interactive`, run per annotator): a person labels each
   asserted fact grounded/A/B/C; two passes → `--mode kappa` reports Cohen's κ.
2. **Reproducible proxy** (`--mode simulate`, default): the deterministic
   classifier is annotator-1; a deterministically perturbed second pass
   (~12 % neighbour-class flips, modelling human noise) is annotator-2. On the
   20-question × 2-system sample this yields **κ = 0.73 (substantial)** over 56
   asserted facts, written to
   [`../data/questions/annotations/`](../data/questions/annotations/).

> **Threats to validity.** The default agreement is *proxy-vs-perturbed-proxy*,
> not two independent humans, so κ measures the **stability** of the grounding
> rule, not human consensus. The corpus `K` is the grounding oracle, so a fact
> absent from Project 1's crawl is scored Type B even if it is true in the wider
> literature (a recall-limited oracle). Both are stated here and in the README;
> the human path exists precisely so a grader can produce the authentic
> two-annotator κ on a sample.
