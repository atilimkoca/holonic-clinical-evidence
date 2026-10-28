# The Context Budget Problem: NP-hardness, Approximation, Complexity

Formal companion to the context-budget component of the generation layer. This
note defines the Context Budget Problem, proves it NP-hard, gives a `1/2`-
approximation with proof, and analyses the retrieval-complexity gap between
holon-bounded and naive GraphRAG. The corresponding measurements are reported
in Sec. 6.4 of the article and Section S9 of the Supplementary Material.

---

## 1. Problem definition

A holon hierarchy supplies candidate context units `h_1, ..., h_n` (holons or
their projection layers). Each `h_i` has a **positive integer token cost**
`t(h_i) in Z_{>0}` and a **nonnegative information value** `v(h_i) in Q_{>=0}`.
Given a nonnegative integer context window budget `L` (the LLM token limit),
the **Context Budget Problem (CBP)** is

```
maximize   Sigma_i v(h_i) * x_i
subject to Sigma_i t(h_i) * x_i <= L,    x_i in {0,1}.
```

This is exactly **0/1 Knapsack** with weights `t` and profits `v`.

---

## 2. NP-hardness

> **Proposition 1.** CBP is NP-hard. Its decision version ("is there a selection
> with value >= V and cost <= L?") is NP-complete.

*Proof.* Membership in NP: a selection `x` is a certificate checkable in `O(n)`.
Hardness by reduction from **SUBSET-SUM**, which is NP-complete. Given a
SUBSET-SUM instance `(a_1, ..., a_n; B)` (does some subset sum to exactly `B`?),
build a CBP instance with `t(h_i) = v(h_i) = a_i` and budget `L = B`, asking
whether value ` >= B` is achievable under cost ` <= B`. Any feasible selection has
`Sigma value = Sigma cost <= B`; achieving value ` >= B` forces `Sigma cost = B`, i.e. a subset
summing to exactly `B`, and conversely. The reduction is polynomial, so CBP is
NP-hard and (with the NP certificate) NP-complete. QED

Hence no polynomial exact algorithm is expected; the production retriever uses
the greedy approximation below, and `dp_knapsack` (pseudo-polynomial `O(nL)`) is
shipped only to *measure* the greedy's quality offline.

---

## 3. A `1/2`-approximation

Before selection, `greedy_knapsack` discards items whose token cost exceeds
`L`. It then returns the better of two candidates: (G) the prefix packed in
decreasing value/token ratio up to the first item that does not fit, and (S)
the single highest-value item that fits.

> **Proposition 2.** `greedy_knapsack` runs in `O(n log n)` and returns value
> ` >= OPT/2`.

*Proof sketch (classical).* Order the remaining items by ratio `v/t` descending
and let `k` be the first index the ratio-fill cannot take because it overflows
`L`. Since items with cost greater than `L` were removed, item `k` fits by
itself. The fractional-knapsack optimum is bounded by the value accumulated up
to and including a *fraction* of item `k`, so `OPT <= V_{<k} + v(h_k)`, where
`V_{<k}` is the value of the greedily packed prefix. Therefore
`OPT <= V_{<k} + v(h_k) <= 2*max(V_{<k}, v(h_k))`. Candidate (G) achieves
` >= V_{<k}` and candidate (S) achieves ` >= v(h_k)`, so
`max(G, S) >= max(V_{<k}, v(h_k)) >= OPT/2`. QED

A fully polynomial-time approximation scheme (**FPTAS**) exists for 0/1 knapsack
(Ibarra-Kim): value ` >= (1-epsilon)*OPT` in `O(n^3/epsilon)` by profit scaling. We do not need
it: the **empirical** ratio of `greedy_knapsack` to `dp_knapsack` in the final
five-budget table is **0.9472 - 1.0000**, with mean approximately **0.973**,
across budgets `L in {100,...,1600}`. This is far above the `1/2` worst-case
bound for the evaluated items, not a general near-optimality guarantee.

---

## 4. Retrieval complexity: holon-based vs naive

> **Proposition 3.** Selecting the context for a query costs `O(|V|)` for naive
> GraphRAG (a scan over all triples) and `O(d * b)` for holon-based retrieval,
> where `d` is the holon-hierarchy depth and `b` the branching factor, under the
> assumption that boundary size is bounded by a constant.

*Argument.* Naive retrieval ranks over every triple/node, so its work is linear
in the graph size `|V|`. Holon-based retrieval descends the `containsHolon`
hierarchy from the query-relevant root, touching only `O(d * b)` projection
summaries and never opening interiors outside the chosen boundary; with bounded
boundary size each visited holon costs `O(1)`. This is the windowing analogue of
Proposition 3 (subgraph extraction bounded by
holon boundaries is polynomial when the boundary is fixed-size).

**Measured.** A naive linear scan over the **14 573**-triple corpus takes
**2.473 ms**; holon-addressed context construction takes **0.110 ms** -- a
reported **22.5x** speedup after rounding. The scalability sweep
(100/500/1000/5000 holons,
synthetic replication, seed 42) shows the decisive structural win is **context
size**, not just wall-clock: System A's average context stays **flat at ~130
tokens** as the corpus grows 50x, whereas System B reaches **587.4 tokens** at
500 holons and remains at that value through the 5,000-holon row. Because LLM
cost and latency scale with context tokens, a
budget-bounded, holon-windowed context is what makes the system scale.

> **Threats to validity.** (i) The lexical TF-IDF retriever ranks in `O(n)` for
> *both* systems, so the sweep's retrieval *wall-clock* is linear for both; the
> `O(d*b)` advantage is realised in context **size** and in the bounded-vs-scan
> microbenchmark, not in the TF-IDF ranking step. A hierarchical index would
> also make A's ranking sublinear. (ii) The 1000/5000-holon points are
> synthetic replications of the 216 real holons (only 216 were crawled); they
> measure *system scaling behaviour*, not new evidence, and
> are reported as such.
