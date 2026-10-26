# §3.6 — Governance-Aware LLM Context (RQ4 contribution)

Same 100 questions, three governance context strategies.

The reported answerability is an access-coverage proxy, not generated-answer accuracy.

| Strategy | Answerability | Mean ctx tokens | Mean cross-holon noise |
|----------|----------|-----------------|------------------------|
| centralized | 1.00 | 233 | 0.00 |
| federated | 1.00 | 308 | 0.00 |
| autonomous | 0.46 | 24 | 0.00 |

- **Token saving**: autonomous (projection-only) uses 9.8x fewer context tokens than centralized.
- **Access trade-off**: centralized/federated answer every question (interior access); autonomous can only answer when the projection summary already names the detail.

## Domain sensitivity (autonomous projection-only answerability)

Per-specialty variation mainly reflects the treatment/efficacy composition of the fixed sample.

| Specialty | Autonomous answerability | Recommended governance |
|-----------|---------------------|------------------------|
| Cardiology | 0.53 | needs interior (centralized/federated) |
| Endocrinology | 0.44 | needs interior (centralized/federated) |
| Gastroenterology | 0.50 | needs interior (centralized/federated) |
| Infectious Disease | 0.45 | needs interior (centralized/federated) |
| Nephrology | 0.40 | needs interior (centralized/federated) |
| Neurology | 0.36 | needs interior (centralized/federated) |
| Oncology | 0.44 | needs interior (centralized/federated) |
| Psychiatry | 0.50 | needs interior (centralized/federated) |
| Pulmonology | 0.40 | needs interior (centralized/federated) |
| Rheumatology | 0.50 | needs interior (centralized/federated) |

**RQ4 finding**: no single topology dominates. Specialties whose projections already carry the requested information type (high autonomous answerability) are well served by cheap projection-only access; detail-critical questions require interior access. A **hybrid** — autonomous for summary-answerable domains, federated/centralized for detail-critical ones — gives the best answerability/token balance, consistent with Data Mesh + SOLID literature. See README.
