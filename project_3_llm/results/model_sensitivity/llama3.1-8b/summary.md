# RQ3 — Holon-Based vs Naive GraphRAG: Controlled Comparison

- Questions: **10**  ·  k = 3  ·  LLM provider: **ollama** (llama3.1:8b)  ·  wall-clock 839.5s


## Deney 1 — SHACL Conformance

| Metric | System A | System B |
|--------|----------|----------|
| First-pass conformance | **100%** | 0% |
| Converged conformance (k=3) | **100%** | 60% |

McNemar (first-pass): discordant A>B=10, B>A=0, p = **1.953e-03** -> REJECT H0.

McNemar (converged): discordant A>B=4, B>A=0, p = **1.250e-01** -> fail to reject H0.

### Convergence curve (fraction conforming by iteration)

| Iteration | System A | System B |
|-----------|----------|----------|
| 0 | 100% | 0% |
| 1 | 100% | 40% |
| 2 | 100% | 60% |

## Deney 2 — Hallucination (Type A/B/C)

| Metric | System A | System B |
|--------|----------|----------|
| Mean hallucination rate | **0.467** | 0.100 |
| Type A / B / C totals | 0 / 10 / 0 | 1 / 1 / 0 |

Assumption check: Shapiro p = 1.336e-04 -> differences non-normal; using **Wilcoxon signed-rank**.

Wilcoxon signed-rank on per-question (B-A): statistic = 4.500, p = **2.092e-02**, Cohen's d = **-1.11** -> REJECT H0.

95% bootstrap CI on hallucination rate: A 0.467 [0.350, 0.550], B 0.100 [0.000, 0.250].

## Deney 3 — Coverage & Token Efficiency

| Metric | System A | System B |
|--------|----------|----------|
| Information coverage | 1.00 | 1.00 |
| Token efficiency (grounded/token) | **0.0007** | 0.0003 |
| Mean context tokens | **128** | 494 |

Coverage (degenerate): p = nan. Token efficiency (paired t-test): p = **4.922e-10**.

## Hypothesis verdict (H3)

- **Conformance**: first-pass 100% (A) vs 0% (B), p=1.95e-03 -> SHACL-guided initialisation raises first-pass conformance; converged conformance remains higher for A (100% vs 60%).
- **Hallucination**: 0.100 (B) -> 0.467 (A), a 367% relative increase (p=2.09e-02). H3's >=30% hallucination reduction is NOT met.

See discussion of converged conformance and the coverage/precision trade-off in the README.
