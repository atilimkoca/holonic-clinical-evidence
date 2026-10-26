# Worked Holon Examples (§2.1 + report appendix)

Three complete four-layer holons, one per holon type, each serialised as **TriG**
so the interior / boundary / projection / context layers are explicit named
graphs. These satisfy the appendix requirement *"en az 3 tam holon örneği (dört
katman ile birlikte)"*.

| # | File | Holon type | Highlights |
|---|------|-----------|------------|
| 1 | [disease_holon_hypertension.trig](disease_holon_hypertension.trig) | `holon:DiseaseHolon` | Diagnostic-criterion SHACL shape on the **boundary** (systolic BP ≥ 130); links to **real MeSH** D006973 |
| 2 | [evidence_chain_holon.trig](evidence_chain_holon.trig) | `holon:EvidenceChainHolon` | Support + causal-link assertions; **aggregate** projection coherent with interior mean |
| 3 | [clinical_question_holon.trig](clinical_question_holon.trig) | `holon:ClinicalQuestionHolon` | Question/answer holon with materialised RDF 1.2 reification, boundary entries, projection summary, and provenance |

All three use the four-layer model `H = ⟨G_int, G_bnd, G_prj, G_ctx⟩` (Definition 1)
and the materialised RDF 1.2 reification pattern documented in the project README.

Parse-check:
```bash
python3 -c "from rdflib import Dataset; \
  ds=Dataset(); ds.parse('disease_holon_hypertension.trig', format='trig'); \
  print(len(list(ds.quads())), 'quads')"
```
