# Integration

This folder contains the group-level end-to-end smoke path required by the
assignment. It wires the existing sub-project APIs together without requiring a
live Neo4J server or external LLM key:

1. Project 1 provides clinical-question holon Turtle files.
2. Project 2 validates those holons with the boundary-aware SHACL set.
3. Project 3 runs the offline natural-language query path and deterministic
   SHACL-guided generation path.

Run from the repository root:

```bash
python -m pytest integration/src/integration_tests.py -q
python integration/src/end_to_end_pipeline.py --sample-size 20
```

The pipeline writes `integration/demo/end_to_end_result.json`.

