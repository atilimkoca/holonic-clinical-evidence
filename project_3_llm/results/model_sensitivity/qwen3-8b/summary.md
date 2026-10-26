# RQ3 — Holon-Based vs Naive GraphRAG: Controlled Comparison

- Questions: **10**  ·  k = 3  ·  LLM provider: **ollama** (qwen3:8b)  ·  wall-clock 726.4s


## Deney 1 — SHACL Conformance

| Metric | System A | System B |
|--------|----------|----------|
| First-pass conformance | **90%** | 0% |
| Converged conformance (k=3) | **100%** | 40% |

McNemar (first-pass): discordant A>B=9, B>A=0, p = **3.906e-03** -> REJECT H0.

McNemar (converged): discordant A>B=6, B>A=0, p = **3.125e-02** -> REJECT H0.

### Convergence curve (fraction conforming by iteration)

| Iteration | System A | System B |
|-----------|----------|----------|
| 0 | 90% | 0% |
| 1 | 100% | 30% |
| 2 | 100% | 40% |

## Deney 2 — Hallucination (Type A/B/C)

| Metric | System A | System B |
|--------|----------|----------|
| Mean hallucination rate | **0.000** | 0.000 |
| Type A / B / C totals | 0 / 0 / 0 | 0 / 0 / 0 |

Assumption check: Shapiro p = nan -> differences non-normal; using **degenerate**.

degenerate on per-question (B-A): statistic = nan, p = **nan**, Cohen's d = **0.00** -> fail to reject H0.

95% bootstrap CI on hallucination rate: A 0.000 [0.000, 0.000], B 0.000 [0.000, 0.000].

## Deney 3 — Coverage & Token Efficiency

| Metric | System A | System B |
|--------|----------|----------|
| Information coverage | 1.00 | 0.80 |
| Token efficiency (grounded/token) | **0.0007** | 0.0002 |
| Mean context tokens | **128** | 494 |

Coverage (degenerate): p = nan. Token efficiency (paired t-test): p = **1.372e-05**.

## Hypothesis verdict (H3)

- **Conformance**: first-pass 90% (A) vs 0% (B), p=3.91e-03 -> SHACL-guided initialisation raises first-pass conformance; converged conformance remains higher for A (100% vs 40%).
- **Hallucination**: 0.000 (B) -> 0.000 (A), a 0% relative reduction (p=nan). H3's >=30% hallucination reduction is NOT met.

See discussion of converged conformance and the coverage/precision trade-off in the README.
