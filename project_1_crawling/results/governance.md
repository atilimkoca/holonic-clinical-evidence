# Governance-Aware Data Architecture (RQ4 — data layer)

Same holonic data deployed under three governance topologies.

## Query latency & completeness

| Query | Centralized (ms) | Federated (ms) | Autonomous (ms) | Autonomous answerable |
|-------|------------------|----------------|-----------------|-----------------------|
| local_treatment | 2.02 | 21.41 | 462.37 | True |
| projection_read | 4.5 | 25.0 | 476.74 | True |
| cross_domain | 11.36 | 93.32 | 2308.87 | True |
| interior_read | 4.66 | 24.72 | 0.0 | False |

Workload completeness — centralized **1.0**, federated **1.0**, autonomous **0.75** (autonomous cannot answer interior-layer queries: projection-only access).

## Schema-evolution cost (Proposition 5 proxy)

- Holons H = 216, domains D = 10
- Centralized re-validations on one shape change: **216** (O(|S|·|H|))
- Federated wall-time (parallel across domains): **21.6**
- Autonomous local re-validations: 216, plus cross-holon alignment pairs **23220** (O(n²))

## Scalability (centralized store)

| #holons | #triples | latency (ms) |
|---------|----------|--------------|
| 50 | 9137 | 6.55 |
| 100 | 10008 | 7.22 |
| 150 | 10886 | 7.79 |
| 216 | 12053 | 7.83 |

## Finding

No single topology dominates. Centralized minimises latency and guarantees global consistency but pays the highest schema-evolution cost; autonomous minimises exposure (projection-only) and update blast-radius but loses interior queryability and incurs O(n²) cross-holon alignment. A **hybrid** — centralized for safety-critical sub-domains (e.g. drug-interactions) and federated/autonomous for general evidence — best fits the medical-evidence domain, supporting H4.