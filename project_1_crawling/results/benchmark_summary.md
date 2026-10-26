# Expressiveness Benchmark — Holonic (Model A) vs Flat (Model B)

- Total queries: **50**
- Answerable on Model A (holonic): **50**
- Answerable on Model B (flat): **40**
- **Expressiveness gain EG(A,B) = 20.0%** (H1 threshold 15%): **H1 SUPPORTED**
- Shared-answerable queries with identical result sets: **40** (result mismatches: none)

## Answerability by category

| Category | #queries | Answerable A | Answerable B |
|----------|----------|--------------|--------------|
| simple | 15 | 15 | 15 |
| medium | 15 | 15 | 15 |
| complex | 10 | 10 | 10 |
| hard | 10 | 10 | 0 |

Model-A-only queries: `H01, H02, H03, H04, H05, H06, H07, H08, H09, H10`

## Information preservation (A <-> B bijection)

- CORE facts: A=11329, B=11329, equal=True
- Canonical assertions: A=204, B=204, equal=True
- **Bijection holds: True** (core diff A\B=0, B\A=0; assertion diff A\B=0, B\A=0)

**Interpretation.** Models A and B encode identical information (the bijection holds), so neither model loses facts. The 20% expressiveness gain is therefore *not* about information content but about *queryability*: the holon-layer / named-graph queries (H01–H10) are answerable directly over Model A's data, whereas Model B does not record the layer partition as data and so cannot answer them without being re-modelled (which would make it non-flat). On the 40 shared queries the two models return identical results, empirically witnessing the bijection.