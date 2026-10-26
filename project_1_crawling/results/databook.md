# DataBook Provenance Chain — Project 1 Data Layer

Generated: 2026-06-07T18:47:50.123558+00:00  ·  offline=True  ·  seed=42
All stages OK: **True**

| # | Stage | Status | Duration (s) | Key output |
|---|-------|--------|--------------|------------|
| 1 | crawl | ok | 0.04 | `data\raw\crawl_summary.json` |
| 2 | extract | ok | 0.04 | `data\processed\holons.json` |
| 3 | transform | ok | 1.66 | `data\rdf\holonic\model_a.trig` |
| 4 | validate_handoff_project2 | ok | 32.54 | `data\rdf\validation_reports\example_setA_report.ttl` |
| 5 | benchmark_expressiveness | ok | 49.77 | `results\expressiveness.csv` |
| 6 | graph_topology | ok | 0.41 | `results\graph_metrics.json` |
| 7 | governance | ok | 19.96 | `results\governance.json` |
| 8 | neo4j_scripts | ok | 0.01 | `results\neo4j\import_holonic.cypher` |

## Step-4 SHACL validation report (Project 2 integration)

- Sampled hand-off holons: 15
- Conforming to **Set A** (boundary-aware): 15 (100%)
- Conforming to **Set B** (flat): 15 (100%)

Each data-producing stage is provenance-tracked with output SHA-1 checksums; the transform output is SHACL-validated against the downstream Project 2 shapes, documenting the hand-off contract.