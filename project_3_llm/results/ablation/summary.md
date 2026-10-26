# RQ3 Ablation — 2x2 Factorial (retrieval x prompt)

- Questions: **100**  ·  k = 3  ·  LLM provider: **mock** (mock-deterministic-v1)  ·  wall-clock 52.3s


| System | Retrieval | Prompt |
|--------|-----------|--------|
| A | boundary | SHACL |
| C | boundary | naive |
| D | naive | SHACL |
| B | naive | naive |

## Per-system metrics

| Metric | System A | System C | System D | System B |
|--------|----------|----------|----------|----------|
| First-pass conformance | 100% | 0% | 66% | 0% |
| Converged conformance (k=3) | 100% | 100% | 66% | 66% |
| Mean hallucination rate | 0.000 | 0.000 | 0.760 | 0.760 |
| Information coverage | 1.00 | 1.00 | 1.00 | 1.00 |
| Mean context tokens | 131 | 131 | 507 | 507 |
| Token efficiency (grounded/token) | 0.0006 | 0.0004 | 0.0004 | 0.0003 |
| Type A / B / C totals | 0 / 0 / 0 | 0 / 0 / 0 | 324 / 0 / 0 | 324 / 0 / 0 |

## Contrasts (one factor isolated per row)

| Contrast | Factor isolated | FP McNemar p | Conv McNemar p | Halluc. test | Halluc. p | Cohen's d |
|----------|-----------------|--------------|----------------|--------------|-----------|-----------|
| A vs C | SHACL prompt | boundary retrieval | 1.578e-30 | 1.000e+00 | degenerate | nan | 0.00 |
| D vs B | SHACL prompt | naive retrieval | 2.711e-20 | 1.000e+00 | degenerate | nan | 0.00 |
| A vs D | boundary retrieval | SHACL prompt | 1.164e-10 | 1.164e-10 | Wilcoxon signed-rank | 2.087e-19 | 23.27 |
| C vs B | boundary retrieval | naive prompt | 1.000e+00 | 1.164e-10 | Wilcoxon signed-rank | 2.087e-19 | 23.27 |
| A vs B | combined (original RQ3 contrast) | 1.578e-30 | 1.164e-10 | Wilcoxon signed-rank | 2.087e-19 | 23.27 |

## Factorial reading

- **Prompt (SHACL) main effect on first-pass conformance**: boundary arm +100% (A-C), naive arm +66% (D-B).
- **Retrieval (boundary) main effect on hallucination**: SHACL arm +0.760 (D-A), naive arm +0.760 (B-C).
- If the SHACL-prompt effect is concentrated in conformance and the boundary-retrieval effect in hallucination, the two design changes are separable and each is individually attributable.
