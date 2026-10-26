# §3.4 — The Context Budget Problem: NP-hardness, Approximation, Complexity

**Project 3 (Student C) — formal companion to
[`../src/context_budget.py`](../src/context_budget.py).** This document defines
the Context Budget Problem, proves it NP-hard, gives a `1/2`-approximation with
proof, and analyses the retrieval-complexity gap between holon-based and naive
GraphRAG. The runnable results are in
[`../results/performance/`](../results/performance/) (knapsack_approx.csv,
latency.csv, scalability.csv) and the figure `../results/figures/scalability.png`.

---

## 1. Problem definition

A holon hierarchy supplies candidate context units `h_1, …, h_n` (holons or
their projection layers). Each `h_i` has a **token cost** `t(h_i) ∈ ℤ⁺` and an
**information value** `v(h_i) ∈ ℚ⁺`. Given a context window budget `L` (the LLM
token limit), the **Context Budget Problem (CBP)** is

```
maximize   Σ_i v(h_i) · x_i
subject to Σ_i t(h_i) · x_i ≤ L,    x_i ∈ {0,1}.
```

This is exactly **0/1 Knapsack** with weights `t` and profits `v`.

---

## 2. NP-hardness

> **Proposition 1.** CBP is NP-hard. Its decision version ("is there a selection
> with value ≥ V and cost ≤ L?") is NP-complete.

*Proof.* Membership in NP: a selection `x` is a certificate checkable in `O(n)`.
Hardness by reduction from **SUBSET-SUM**, which is NP-complete. Given a
SUBSET-SUM instance `(a_1, …, a_n; B)` (does some subset sum to exactly `B`?),
build a CBP instance with `t(h_i) = v(h_i) = a_i` and budget `L = B`, asking
whether value `≥ B` is achievable under cost `≤ B`. Any feasible selection has
`Σ value = Σ cost ≤ B`; achieving value `≥ B` forces `Σ cost = B`, i.e. a subset
summing to exactly `B`, and conversely. The reduction is polynomial, so CBP is
NP-hard and (with the NP certificate) NP-complete. ∎

Hence no polynomial exact algorithm is expected; the production retriever uses
the greedy approximation below, and `dp_knapsack` (pseudo-polynomial `O(nL)`) is
shipped only to *measure* the greedy's quality offline.

---

## 3. A `1/2`-approximation

`greedy_knapsack` returns the better of two candidates: (G) fill by decreasing
value/token ratio, and (S) the single highest-value item that fits.

> **Proposition 2.** `greedy_knapsack` runs in `O(n log n)` and returns value
> `≥ OPT/2`.

*Proof sketch (classical).* Order items by ratio `v/t` descending and let `k` be
the first index the ratio-fill cannot take because it overflows `L`. The
fractional-knapsack optimum is bounded by the value accumulated up to and
including a *fraction* of item `k`, so `OPT ≤ V_{<k} + v(h_k)`, where `V_{<k}` is
the value of the greedily packed prefix. Therefore
`OPT ≤ V_{<k} + v(h_k) ≤ 2·max(V_{<k}, v(h_k))`. Candidate (G) achieves
`≥ V_{<k}` and candidate (S) achieves `≥ v(h_k)` (item `k` fits since it alone
respects `L` in the integral instance whenever `t(h_k) ≤ L`), so
`max(G, S) ≥ max(V_{<k}, v(h_k)) ≥ OPT/2`. ∎

A fully polynomial-time approximation scheme (**FPTAS**) exists for 0/1 knapsack
(Ibarra–Kim): value `≥ (1−ε)·OPT` in `O(n³/ε)` by profit scaling. We do not need
it: the **empirical** ratio of `greedy_knapsack` to `dp_knapsack` on the
100-holon corpus is **0.975 – 1.000** across budgets `L ∈ {100,…,1600}`
(`knapsack_approx.csv`), i.e. far above the `1/2` worst-case bound, because real
holon costs/values are not adversarial.

---

## 4. Retrieval complexity: holon-based vs naive

> **Proposition 3.** Selecting the context for a query costs `O(|V|)` for naive
> GraphRAG (a scan over all triples) and `O(d · b)` for holon-based retrieval,
> where `d` is the holon-hierarchy depth and `b` the branching factor, under the
> assumption that boundary size is bounded by a constant.

*Argument.* Naive retrieval ranks over every triple/node, so its work is linear
in the graph size `|V|`. Holon-based retrieval descends the `containsHolon`
hierarchy from the query-relevant root, touching only `O(d · b)` projection
summaries and never opening interiors outside the chosen boundary; with bounded
boundary size each visited holon costs `O(1)`. This is the windowing analogue of
Proposition 3 in the assignment's framework (subgraph extraction bounded by
holon boundaries is polynomial when the boundary is fixed-size).

**Measured (`latency.csv`).** A naive linear scan over the **14 573**-triple
corpus takes **2.57 ms**; holon-bounded context construction takes **0.114 ms** —
a **22.6×** speedup. The `scalability.png` sweep (100/500/1000/5000 holons,
synthetic replication, seed 42) shows the decisive structural win is **context
size**, not just wall-clock: System A's average context stays **flat at ~130
tokens** as the corpus grows 50×, whereas System B's grows and saturates at
~566 tokens. Because LLM cost and latency scale with context tokens, a
budget-bounded, holon-windowed context is what makes the system scale.

> **Threats to validity.** (i) The lexical TF-IDF retriever ranks in `O(n)` for
> *both* systems, so the sweep's retrieval *wall-clock* is linear for both; the
> `O(d·b)` advantage is realised in context **size** and in the bounded-vs-scan
> microbenchmark, not in the TF-IDF ranking step. A hierarchical index would
> also make A's ranking sublinear. (ii) The 1000/5000-holon points are
> synthetic replications of the 216 real holons (only 216 were crawled by
> Project 1); they measure *syststem scaling behaviour*, not new evidence, and
> are reported as such.
