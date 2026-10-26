# RQ2 — Boundary-Aware vs Flat SHACL: Detection Comparison

- Corpus size: **100** holons (50 inconsistent, 50 consistent)

- Validation latency (total): Set A 7.2s, Set B 5.1s


## Per-type Recall (detection rate)

| Type | Set A recall | Set B recall | Set A F1 | Set B F1 |
|------|-------------|-------------|----------|----------|
| T1 | 1.00 | 1.00 | 1.00 | 1.00 |
| T2 | 1.00 | 1.00 | 1.00 | 1.00 |
| T3 | 1.00 | 1.00 | 1.00 | 1.00 |
| T4 | 1.00 | 0.00 | 1.00 | 0.00 |
| T5 | 1.00 | 0.00 | 1.00 | 0.00 |
| T6 | 1.00 | 0.00 | 1.00 | 0.00 |
| ALL | 1.00 | 0.52 | 1.00 | 0.68 |

## McNemar's Test (paired correctness, Set A vs Set B)

|              | B correct | B wrong |
|--------------|-----------|---------|
| **A correct**| 76 | 24 |
| **A wrong**  | 0 | 0 |

- Discordant pairs: A-right/B-wrong = **24**, A-wrong/B-right = **0**
- Test statistic = **0.0**, p-value = **1.192e-07**
- **Verdict:** REJECT H0 — the two sets differ significantly (p < 0.05).


## 95% Bootstrap Confidence Intervals (recall on inconsistent holons)

| Quantity | Point estimate | 95% CI |
|----------|----------------|--------|
| Set A recall | 1.00 | [1.00, 1.00] |
| Set B recall | 0.52 | [0.38, 0.66] |
| Recall difference (A−B) | 0.48 | [0.34, 0.62] |

The difference CI excludes 0 → the boundary-aware advantage is significant and supports **H₂** (≥25% more inconsistencies detected; observed +48 pp).


## Interpretation

Set A and Set B are statistically equivalent on T1–T3 (structural / referential / temporal), as designed. The boundary-aware set's advantage is concentrated in T4 (semantic admissibility), T5 (cross-holon contradiction) and T6 (projection–interior incoherence) — exactly the classes that require the holon context deliberately removed from the stated flat baseline.
