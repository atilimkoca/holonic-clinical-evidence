# RQ3 — Holon-Based vs Naive GraphRAG: Controlled Comparison

- Questions: **100**  ·  k = 3  ·  LLM provider: **mock** (mock-deterministic-v1)  ·  wall-clock 26.5s


## Deney 1 — SHACL Conformance

| Metric | System A | System B |
|--------|----------|----------|
| First-pass conformance | **100%** | 0% |
| Converged conformance (k=3) | **100%** | 66% |

McNemar (first-pass): discordant A>B=100, B>A=0, p = **1.578e-30** -> REJECT H0.

McNemar (converged): discordant A>B=34, B>A=0, p = **1.164e-10** -> REJECT H0.

### Convergence curve (fraction conforming by iteration)

| Iteration | System A | System B |
|-----------|----------|----------|
| 0 | 100% | 0% |
| 1 | 100% | 66% |
| 2 | 100% | 66% |

## Deney 2 — Hallucination (Type A/B/C)

| Metric | System A | System B |
|--------|----------|----------|
| Mean hallucination rate | **0.000** | 0.760 |
| Type A / B / C totals | 0 / 0 / 0 | 324 / 0 / 0 |

Assumption check: Shapiro p = 5.374e-13 -> differences non-normal; using **Wilcoxon signed-rank**.

Wilcoxon signed-rank on per-question (B-A): statistic = 0.000, p = **2.087e-19**, Cohen's d = **23.27** -> REJECT H0.

95% bootstrap CI on hallucination rate: A 0.000 [0.000, 0.000], B 0.760 [0.754, 0.766].

## Deney 3 — Coverage & Token Efficiency

| Metric | System A | System B |
|--------|----------|----------|
| Information coverage | 1.00 | 1.00 |
| Token efficiency (grounded/token) | **0.0006** | 0.0003 |
| Mean context tokens | **131** | 507 |

Coverage (degenerate): p = nan. Token efficiency (Wilcoxon signed-rank): p = **3.896e-18**.

## Hypothesis verdict (H3)

- **Conformance**: first-pass 100% (A) vs 0% (B), p=1.58e-30 -> SHACL-guided initialisation raises first-pass conformance; converged conformance remains higher for A (100% vs 66%).
- **Hallucination**: 0.760 (B) -> 0.000 (A), a 100% relative reduction (p=2.09e-19). H3's >=30% hallucination reduction is SUPPORTED.

See discussion of converged conformance and the coverage/precision trade-off in the README.
