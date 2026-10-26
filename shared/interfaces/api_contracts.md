# API Contracts — Inter-Project Interfaces

This document defines the interfaces between the three sub-projects to ensure smooth integration.

---

## Project 1 → Project 2: Data Layer to Semantic Layer

### Output Format
Project 1 must produce RDF data in **Turtle 1.2** format conforming to the shared ontology.

### File Convention
```
data/rdf/clinical_questions/       # One .ttl file per question holon
data/rdf/entities/diseases.ttl     # All disease entities
data/rdf/entities/drugs.ttl        # All drug entities
data/rdf/entities/sources.ttl      # All evidence sources
data/rdf/relationships.ttl         # Cross-entity relationships with reification
```

### Required Metadata per Record
Every clinical question record must include:
- `oe:questionText` — the question string
- `oe:answerText` — the AI-generated answer
- `holon:recordedOn` — crawl date
- `oe:cites` — at least one evidence source
- Reification with `holon:confidence` on each `oe:treats` / `oe:supports` triple

### Neo4J Access
- Bolt protocol: `bolt://localhost:7687`
- Database: `openevidence`
- Read-only credentials shared via environment variable `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASS`

---

## Project 2 → Project 3: Semantic Layer to LLM Layer

### SHACL Shapes Location
```
project_2_semantic/shacl/shapes/    # All .ttl shape files
```

### Shape Naming Convention
- Node shapes: `oe:{EntityName}Shape` (e.g., `oe:DiseaseShape`)
- Property shapes: `oe:{EntityName}Shape-{property}` (e.g., `oe:DiseaseShape-hasSymptom`)
- Reifier shapes: `oe:{EntityName}ReifierShape`

### Validation API (Python)
```python
from project_2_semantic.src.shacl_validator import validate_graph

# Returns (conforms: bool, report_graph: str, violations: list[dict])
conforms, report_ttl, violations = validate_graph(
    data_path="path/to/data.ttl",
    shapes_path="path/to/shapes/",
    severity_threshold="sh:Warning"  # minimum severity to report
)
```

### Holon Builder API
```python
from project_2_semantic.src.holon_builder import build_holon

# Constructs a four-layer holon from raw entity data
holon_ttl = build_holon(
    holon_type="ClinicalQuestionHolon",
    interior_data={"question": "...", "answer": "...", "citations": [...]},
    boundary_shapes=["oe:ClinicalQuestionShape"],
    context_metadata={"source": "openevidence.com", "crawl_date": "2025-06-01"}
)
```

---

## Project 3 → Project 1 & 2: LLM Layer Feedback

### Generated RDF Output
LLM-generated triples must be written to:
```
project_3_llm/results/generated_rdf/   # LLM-produced .ttl files
```

These files will be validated by Project 2's SHACL validator before integration.

### Query Interface
```python
from project_3_llm.src.neo4j_query import natural_language_query

# Translates natural language to Cypher, executes, returns structured result
result = natural_language_query(
    question="What drugs treat hypertension with Level 1A evidence?",
    max_hops=3,
    include_confidence=True
)
```

---

## Shared Constants

### Namespaces (prefixes.ttl)
All projects must use the shared prefix file at `shared/ontology/prefixes.ttl`.

### Confidence Scale
- `[0.0, 0.3)` — Low confidence
- `[0.3, 0.7)` — Moderate confidence  
- `[0.7, 0.9)` — High confidence
- `[0.9, 1.0]` — Very high confidence

### Evidence Level Mapping
| Level | Description | Numeric Score |
|-------|-------------|---------------|
| 1A | Systematic Review of RCTs | 0.95 |
| 1B | Individual RCT | 0.90 |
| 2A | Systematic Review of Cohort | 0.80 |
| 2B | Individual Cohort Study | 0.70 |
| 3 | Case-Control Studies | 0.55 |
| 4 | Case Series | 0.40 |
| 5 | Expert Opinion | 0.25 |

---

## Integration Test Protocol

1. Project 1 produces 20 sample holons → saved to `shared/test_data/`
2. Project 2 validates these holons and produces reports
3. Project 3 queries and generates new knowledge from these holons
4. End-to-end test: single question → crawl → RDF → validate → query → answer
