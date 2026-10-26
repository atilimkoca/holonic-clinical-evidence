# §2.6 — OWL → SHACL Conversion Loss Report

Source: `medical_subset.ttl`

- Convertible axioms: **9**
- Lossy axioms: **5**
- **Completeness = 64%**


## Converted (faithful SHACL encoding)

- subClassOf(Antibiotic,Drug) -> structural (sh:class honours it)
- disjointWith(Drug,Disease) -> sh:not [sh:class Disease]
- domain/range(hasSymptom) -> sh:property[sh:class Symptom]
- domain/range(interactsWith) -> sh:property[sh:class Drug]
- range(hasAtcCode,string) -> sh:datatype
- domain/range(treats) -> sh:property[sh:class Disease]
- FunctionalProperty(hasAtcCode) -> sh:maxCount 1
- someValuesFrom(hasSymptom,Symptom) -> sh:qualifiedValueShape minCount 1
- cardinality(hasAtcCode)=1 -> sh:minCount/maxCount

## Lossy residue (no validation-equivalent SHACL)

| OWL axiom | Detail | Why it cannot convert |
|-----------|--------|------------------------|
| `equivalentClass` | Medication ≡ Drug | SHACL has no class-equivalence axiom; cannot entail mutual membership. |
| `inverseOf` | treatedBy ⁻¹ treats | SHACL validates existing triples but cannot ENTAIL the inverse edge. |
| `TransitiveProperty` | partOf | No transitive-closure entailment; paths validate reachability, not inference. |
| `SymmetricProperty` | interactsWith | Cannot entail the symmetric triple; only validate if already present. |
| `sameAs` | aspirin = acetylsalicylicAcid | SHACL has no identity reasoning / individual merging. |

## Why the loss is structural
Every lossy axiom is an **entailment** axiom: it licenses the inference of triples that are not asserted (an inverse edge, a transitive hop, an identity merge, a class equivalence). SHACL's semantics is **closed-graph validation** — it checks the triples present, it never derives new ones. The convertible axioms are exactly the **constraint** axioms (cardinality, domain/range typing, disjointness, existential/universal restrictions), which map to shape conditions. Hence the OWL→SHACL frontier coincides with the **entailment vs constraint** boundary, and completeness < 100% is *inherent*, not a tool limitation.
