# RQ3 — Holon-Based vs Naive GraphRAG: Controlled Comparison

- Questions: **10**  ·  k = 3  ·  LLM provider: **ollama** (gemma3:4b)  ·  wall-clock 408.3s


## Deney 1 — SHACL Conformance

| Metric | System A | System B |
|--------|----------|----------|
| First-pass conformance | **50%** | 0% |
| Converged conformance (k=3) | **60%** | 0% |

McNemar (first-pass): discordant A>B=5, B>A=0, p = **6.250e-02** -> fail to reject H0.

McNemar (converged): discordant A>B=6, B>A=0, p = **3.125e-02** -> REJECT H0.

### Convergence curve (fraction conforming by iteration)

| Iteration | System A | System B |
|-----------|----------|----------|
| 0 | 50% | 0% |
| 1 | 60% | 0% |
| 2 | 60% | 0% |

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
| Information coverage | 0.60 | 0.00 |
| Token efficiency (grounded/token) | **0.0004** | 0.0000 |
| Mean context tokens | **128** | 494 |

Coverage (degenerate): p = nan. Token efficiency (Wilcoxon signed-rank): p = **2.771e-02**.

## Hypothesis verdict (H3)

- **Conformance**: first-pass 50% (A) vs 0% (B), p=6.25e-02 -> SHACL-guided initialisation raises first-pass conformance; converged conformance remains higher for A (60% vs 0%).
- **Hallucination**: 0.000 (B) -> 0.000 (A), a 0% relative reduction (p=nan). H3's >=30% hallucination reduction is NOT met.

See discussion of converged conformance and the coverage/precision trade-off in the README.
