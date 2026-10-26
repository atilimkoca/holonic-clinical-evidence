# Complexity Analysis — Data Layer

Collects the complexity arguments for Project 1 and ties each to a framework
proposition and to a measured quantity.

Notation: `n` triples, `H` holons, `b = n/|H|` mean holon size, `d` hierarchy
depth, `|S|` shapes, `D` governance domains, `Σ` signature alphabet.

## 1. Query answering (holonic vs flat)

| Query class | Model A (holonic) | Model B (flat) | Note |
|-------------|-------------------|----------------|------|
| entity lookup (simple) | `Θ(1)`–`Θ(n)` scan | same | identical base triples |
| edge metadata (medium/complex) | `Θ(1)` joins/edge (reifier+triple-term) | `Θ(1)` joins/edge (`rdf:Statement`) | constant-factor idiom difference, **not** asymptotic |
| layer/graph-scoped (hard) | `Θ(|G_ℓ^h|)` graph lookup | **not answerable as data** | the 20% expressiveness gain (`benchmark_summary.md`) |

So the holonic model is **never asymptotically worse** for the benchmark and is
strictly more expressive on the layer class. Measured per-query latencies
(`results/expressiveness.csv`, `ms_A`/`ms_B`) confirm the two stores are within a
small constant factor on shared queries.

## 2. Information-preservation check

Computing the canonical `(CORE, ASRT)` invariants and comparing is
`Θ(n)` (one pass per model + set comparison). Implemented in
`benchmark.check_information_preservation`; the proof that this decides the
bijection is in [`information_preservation.md`](information_preservation.md).

## 3. Holon-level graph construction & analysis

- Construction via inverted entity index: `Σ_e (k_e choose 2)` edges where `k_e`
  is the number of holons sharing entity `e`; worst case `O(|H|²)` but in
  practice sparse (measured: 216 nodes, 639 edges).
- Betweenness centrality (Brandes): `O(V·E)` for unweighted, `O(V·E + V²log V)`
  weighted — fine at this scale (sub-second, `results/graph_metrics.json`).
- Community detection (greedy modularity / CNM): `O(V·log²V)` typical.
- NMI / ARI / purity vs specialty: `Θ(V)` over the contingency table.

## 4. Holon homomorphism & subsumption

- Pattern match `P ⤳ h` is a subset test: `O(|P|)` per holon, `O(|H|·|P|)` for a
  pattern over the corpus.
- Subsumption is signature set-inclusion: pairwise `O(|H|² · |Σ|)`; the
  signature lattice is a partial order (reflexive/antisymmetric/transitive).
- General (graph, not signature) holon homomorphism is the
  subgraph-homomorphism problem, **NP-complete**; restricting to bounded-size
  projection signatures (as we do) makes it polynomial — the holon-boundary
  analogue of framework Proposition 3 (bounded boundaries ⇒ polynomial subgraph
  matching).

## 5. Conformance checking (framework Proposition 2)

SHACL conformance over a holon hierarchy: `O(d · b · |S|)` for core constraints;
**PSPACE-hard** in general once `sh:sparql` constraints are present (SPARQL
evaluation is PSPACE-complete). The integration check validates the full
216-holon hand-off against Project 2's Set A with 0 violations
(`results/databook.md`), empirically tractable at this scale (~33 s).

## 6. Governance trade-off (framework Proposition 5)

| Topology | Schema-evolution cost | Cross-holon consistency | Exposure |
|----------|----------------------|--------------------------|----------|
| Centralized | `O(|S|·|H|)` re-validate all | trivial (global) | full |
| Federated | `O(|S|·|H|)` serial, `O(|S|·|H|/D)` wall | shared boundary | domain |
| Autonomous | `O(|H|)` local + `O(|H|²)` alignment | eventual, pairwise | projection-only |

Measured (`results/governance.json`, `H=216`, `D=10`): centralized 216
re-validations; autonomous `H(H−1)/2 = 23 220` alignment pairs and workload
completeness 0.75 (interior queries unanswerable under projection-only access).
This realises the `O(n²)` interoperability cost of full autonomy vs. the
`O(|S|·|H|)` evolution cost of centralisation, and motivates the hybrid model
(H₄).

## 7. Summary

The holonic model adds named-graph structure at **no asymptotic query cost** and
a modest constant space overhead (Model A 14 573 vs Model B 13 505 triples,
≈ +8%), while enabling a class of layer/provenance queries the flat model cannot
answer as data. The added structure pays its way in expressiveness (20% gain)
without sacrificing information (bijection holds).
