# RQ3 Ablation — 2x2 Factorial (retrieval x prompt)

- Questions: **10**  ·  k = 3  ·  LLM provider: **ollama** (gemma3:4b)  ·  wall-clock 462.4s


| System | Retrieval | Prompt |
|--------|-----------|--------|
| A | boundary | SHACL |
| C | boundary | naive |
| D | naive | SHACL |
| B | naive | naive |

## Per-system metrics

| Metric | System A | System C | System D | System B |
|--------|----------|----------|----------|----------|
| First-pass conformance | 50% | 0% | 30% | 0% |
| Converged conformance (k=3) | 60% | 0% | 30% | 0% |
| Mean hallucination rate | 0.000 | 0.000 | 0.000 | 0.000 |
| Information coverage | 0.60 | 0.00 | 0.10 | 0.00 |
| Mean context tokens | 128 | 128 | 494 | 494 |
| Token efficiency (grounded/token) | 0.0004 | 0.0000 | 0.0001 | 0.0000 |
| Type A / B / C totals | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |

## Contrasts (one factor isolated per row)

| Contrast | Factor isolated | FP McNemar p | Conv McNemar p | Halluc. test | Halluc. p | Cohen's d |
|----------|-----------------|--------------|----------------|--------------|-----------|-----------|
| A vs C | SHACL prompt | boundary retrieval | 6.250e-02 | 3.125e-02 | degenerate | nan | 0.00 |
| D vs B | SHACL prompt | naive retrieval | 2.500e-01 | 2.500e-01 | degenerate | nan | 0.00 |
| A vs D | boundary retrieval | SHACL prompt | 6.875e-01 | 4.531e-01 | degenerate | nan | 0.00 |
| C vs B | boundary retrieval | naive prompt | 1.000e+00 | 1.000e+00 | degenerate | nan | 0.00 |
| A vs B | combined (original RQ3 contrast) | 6.250e-02 | 3.125e-02 | degenerate | nan | 0.00 |

## Factorial reading

- **Prompt (SHACL) main effect on first-pass conformance**: boundary arm +50% (A-C), naive arm +30% (D-B).
- **Retrieval (boundary) main effect on hallucination**: SHACL arm +0.000 (D-A), naive arm +0.000 (B-C).
- If the SHACL-prompt effect is concentrated in conformance and the boundary-retrieval effect in hallucination, the two design changes are separable and each is individually attributable.
