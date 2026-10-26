# RQ2 Extended — Boundary-Aware (A) vs Flat (B) vs Flat + Context-Aware SPARQL (C)

- Corpus size: **100** holons (50 inconsistent, 50 consistent)
- Set A and Set B validate the holonic serialisation; Set C validates the flat-RDF export (src/flatten_corpus.py).
- Validation latency (total): Set A 7.5s, Set B 5.3s, Set C 10.2s


## Per-type Recall / F1

| Type | A recall | B recall | C recall | A F1 | B F1 | C F1 |
|------|----------|----------|----------|------|------|------|
| T1 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| T2 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| T3 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| T4 | 1.00 | 0.00 | 1.00 | 1.00 | 0.00 | 1.00 |
| T5 | 1.00 | 0.00 | 1.00 | 1.00 | 0.00 | 1.00 |
| T6 | 1.00 | 0.00 | 1.00 | 1.00 | 0.00 | 1.00 |
| ALL | 1.00 | 0.52 | 1.00 | 1.00 | 0.68 | 1.00 |

## Pairwise McNemar (paired correctness)

| Pair | Discordant (x-right/y-wrong) | Discordant (x-wrong/y-right) | statistic | p |
|------|------------------------------|------------------------------|-----------|---|
| A vs B | 24 | 0 | 0.0 | 1.192e-07 |
| A vs C | 0 | 0 | 0.0 | 1.000e+00 |
| C vs B | 24 | 0 | 0.0 | 1.192e-07 |

## 95% Bootstrap CIs (recall on inconsistent holons)

| Quantity | Point estimate | 95% CI |
|----------|----------------|--------|
| Set A recall | 1.00 | [1.00, 1.00] |
| Set B recall | 0.52 | [0.38, 0.66] |
| Set C recall | 1.00 | [1.00, 1.00] |
| Recall difference (A-B) | 0.48 | [0.34, 0.62] |
| Recall difference (A-C) | 0.00 | [0.00, 0.00] |
| Recall difference (C-B) | 0.48 | [0.34, 0.62] |

## Interpretation

Set C measures how much of Set A's detection advantage a context-aware SPARQL author can recover WITHOUT the boundary representation. Its T4a check hard-codes the schema-level 0.50 threshold (the per-holon admission rule is not representable in flat RDF), and its T5/T6 checks survive only because the flat export retains holon-membership and aggregate-summary facts. Detection parity with Set A therefore does NOT make the two designs equivalent: the recovered checks are corpus-specific constants and leftover facts rather than a reusable boundary contract, and the same boundary additionally serves retrieval, LLM grounding, projection and governance (RQ3/RQ4).
