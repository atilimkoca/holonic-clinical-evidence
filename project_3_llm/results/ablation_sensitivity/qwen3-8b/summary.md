# RQ3 Ablation — 2x2 Factorial (retrieval x prompt)

- Questions: **10**  ·  k = 3  ·  LLM provider: **ollama** (qwen3:8b)  ·  wall-clock 897.4s


| System | Retrieval | Prompt |
|--------|-----------|--------|
| A | boundary | SHACL |
| C | boundary | naive |
| D | naive | SHACL |
| B | naive | naive |

## Per-system metrics

| Metric | System A | System C | System D | System B |
|--------|----------|----------|----------|----------|
| First-pass conformance | 90% | 0% | 100% | 0% |
| Converged conformance (k=3) | 100% | 20% | 100% | 40% |
| Mean hallucination rate | 0.000 | 0.000 | 0.000 | 0.000 |
| Information coverage | 1.00 | 0.70 | 1.00 | 0.80 |
| Mean context tokens | 128 | 128 | 494 | 494 |
| Token efficiency (grounded/token) | 0.0007 | 0.0002 | 0.0006 | 0.0002 |
| Type A / B / C totals | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |

## Contrasts (one factor isolated per row)

| Contrast | Factor isolated | FP McNemar p | Conv McNemar p | Halluc. test | Halluc. p | Cohen's d |
|----------|-----------------|--------------|----------------|--------------|-----------|-----------|
| A vs C | SHACL prompt | boundary retrieval | 3.906e-03 | 7.812e-03 | degenerate | nan | 0.00 |
| D vs B | SHACL prompt | naive retrieval | 1.953e-03 | 3.125e-02 | degenerate | nan | 0.00 |
| A vs D | boundary retrieval | SHACL prompt | 1.000e+00 | 1.000e+00 | degenerate | nan | 0.00 |
| C vs B | boundary retrieval | naive prompt | 1.000e+00 | 6.250e-01 | degenerate | nan | 0.00 |
| A vs B | combined (original RQ3 contrast) | 3.906e-03 | 3.125e-02 | degenerate | nan | 0.00 |

## Factorial reading

- **Prompt (SHACL) main effect on first-pass conformance**: boundary arm +90% (A-C), naive arm +100% (D-B).
- **Retrieval (boundary) main effect on hallucination**: SHACL arm +0.000 (D-A), naive arm +0.000 (B-C).
- If the SHACL-prompt effect is concentrated in conformance and the boundary-retrieval effect in hallucination, the two design changes are separable and each is individually attributable.
