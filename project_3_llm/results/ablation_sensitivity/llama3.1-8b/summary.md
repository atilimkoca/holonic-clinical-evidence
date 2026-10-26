# RQ3 Ablation — 2x2 Factorial (retrieval x prompt)

- Questions: **10**  ·  k = 3  ·  LLM provider: **ollama** (llama3.1:8b)  ·  wall-clock 807.4s


| System | Retrieval | Prompt |
|--------|-----------|--------|
| A | boundary | SHACL |
| C | boundary | naive |
| D | naive | SHACL |
| B | naive | naive |

## Per-system metrics

| Metric | System A | System C | System D | System B |
|--------|----------|----------|----------|----------|
| First-pass conformance | 100% | 0% | 100% | 0% |
| Converged conformance (k=3) | 100% | 20% | 100% | 60% |
| Mean hallucination rate | 0.467 | 0.000 | 0.133 | 0.100 |
| Information coverage | 1.00 | 0.80 | 1.00 | 1.00 |
| Mean context tokens | 128 | 128 | 494 | 494 |
| Token efficiency (grounded/token) | 0.0007 | 0.0002 | 0.0006 | 0.0003 |
| Type A / B / C totals | 0 / 10 / 0 | 0 / 0 / 0 | 0 / 4 / 0 | 1 / 1 / 0 |

## Contrasts (one factor isolated per row)

| Contrast | Factor isolated | FP McNemar p | Conv McNemar p | Halluc. test | Halluc. p | Cohen's d |
|----------|-----------------|--------------|----------------|--------------|-----------|-----------|
| A vs C | SHACL prompt | boundary retrieval | 1.953e-03 | 7.812e-03 | Wilcoxon signed-rank | 3.892e-03 | -2.86 |
| D vs B | SHACL prompt | naive retrieval | 1.953e-03 | 1.250e-01 | Wilcoxon signed-rank | 4.576e-01 | -0.09 |
| A vs D | boundary retrieval | SHACL prompt | 1.000e+00 | 1.000e+00 | Wilcoxon signed-rank | 1.700e-02 | -1.12 |
| C vs B | boundary retrieval | naive prompt | 1.000e+00 | 2.891e-01 | degenerate | nan | 0.50 |
| A vs B | combined (original RQ3 contrast) | 1.953e-03 | 1.250e-01 | Wilcoxon signed-rank | 2.092e-02 | -1.11 |

## Factorial reading

- **Prompt (SHACL) main effect on first-pass conformance**: boundary arm +100% (A-C), naive arm +100% (D-B).
- **Retrieval (boundary) main effect on hallucination**: SHACL arm -0.333 (D-A), naive arm +0.100 (B-C).
- If the SHACL-prompt effect is concentrated in conformance and the boundary-retrieval effect in hallucination, the two design changes are separable and each is individually attributable.
