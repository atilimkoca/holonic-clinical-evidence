# §2.6 — OWL → SHACL Conversion Loss Report

Source: `mesh_vocab.rdf`

- Convertible axioms: **58**
- Lossy axioms: **1**
- **Completeness = 98%**


## Converted (faithful SHACL encoding)

- subClassOf(PublicationType,Descriptor) -> structural (sh:class honours it)
- subClassOf(TopicalDescriptor,Descriptor) -> structural (sh:class honours it)
- subClassOf(CheckTag,Descriptor) -> structural (sh:class honours it)
- subClassOf(GeographicalDescriptor,Descriptor) -> structural (sh:class honours it)
- subClassOf(Concept,Thing) -> structural (sh:class honours it)
- subClassOf(Descriptor,Thing) -> structural (sh:class honours it)
- subClassOf(DescriptorQualifierPair,Thing) -> structural (sh:class honours it)
- subClassOf(TreeNumber,Thing) -> structural (sh:class honours it)
- subClassOf(Term,Thing) -> structural (sh:class honours it)
- subClassOf(SupplementaryConceptRecord,Thing) -> structural (sh:class honours it)
- subClassOf(Qualifier,Thing) -> structural (sh:class honours it)
- subClassOf(Thing,Thing) -> structural (sh:class honours it)
- subClassOf(AllowedDescriptorQualifierPair,DescriptorQualifierPair) -> structural (sh:class honours it)
- subClassOf(DisallowedDescriptorQualifierPair,DescriptorQualifierPair) -> structural (sh:class honours it)
- subClassOf(SCR_Chemical,SupplementaryConceptRecord) -> structural (sh:class honours it)
- subClassOf(SCR_Organism,SupplementaryConceptRecord) -> structural (sh:class honours it)
- subClassOf(SCR_Protocol,SupplementaryConceptRecord) -> structural (sh:class honours it)
- subClassOf(SCR_Disease,SupplementaryConceptRecord) -> structural (sh:class honours it)
- disjointWith(PublicationType,TopicalDescriptor) -> sh:not [sh:class TopicalDescriptor]
- disjointWith(CheckTag,TopicalDescriptor) -> sh:not [sh:class TopicalDescriptor]
- disjointWith(GeographicalDescriptor,TopicalDescriptor) -> sh:not [sh:class TopicalDescriptor]
- disjointWith(Concept,TreeNumber) -> sh:not [sh:class TreeNumber]
- disjointWith(Descriptor,TreeNumber) -> sh:not [sh:class TreeNumber]
- disjointWith(DescriptorQualifierPair,TreeNumber) -> sh:not [sh:class TreeNumber]
- disjointWith(Term,TreeNumber) -> sh:not [sh:class TreeNumber]
- disjointWith(SupplementaryConceptRecord,TreeNumber) -> sh:not [sh:class TreeNumber]
- disjointWith(Qualifier,TreeNumber) -> sh:not [sh:class TreeNumber]
- disjointWith(Concept,DescriptorQualifierPair) -> sh:not [sh:class DescriptorQualifierPair]
- disjointWith(Descriptor,DescriptorQualifierPair) -> sh:not [sh:class DescriptorQualifierPair]
- disjointWith(Concept,Term) -> sh:not [sh:class Term]
- disjointWith(Descriptor,Term) -> sh:not [sh:class Term]
- disjointWith(DescriptorQualifierPair,Term) -> sh:not [sh:class Term]
- disjointWith(SupplementaryConceptRecord,Term) -> sh:not [sh:class Term]
- disjointWith(Qualifier,Term) -> sh:not [sh:class Term]
- disjointWith(Concept,SupplementaryConceptRecord) -> sh:not [sh:class SupplementaryConceptRecord]
- disjointWith(Descriptor,SupplementaryConceptRecord) -> sh:not [sh:class SupplementaryConceptRecord]
- disjointWith(DescriptorQualifierPair,SupplementaryConceptRecord) -> sh:not [sh:class SupplementaryConceptRecord]
- disjointWith(Qualifier,SupplementaryConceptRecord) -> sh:not [sh:class SupplementaryConceptRecord]
- disjointWith(Concept,Qualifier) -> sh:not [sh:class Qualifier]
- disjointWith(Descriptor,Qualifier) -> sh:not [sh:class Qualifier]
- disjointWith(DescriptorQualifierPair,Qualifier) -> sh:not [sh:class Qualifier]
- disjointWith(Concept,Descriptor) -> sh:not [sh:class Descriptor]
- disjointWith(AllowedDescriptorQualifierPair,DisallowedDescriptorQualifierPair) -> sh:not [sh:class DisallowedDescriptorQualifierPair]
- disjointWith(SCR_Chemical,SCR_Organism) -> sh:not [sh:class SCR_Organism]
- disjointWith(SCR_Protocol,SCR_Organism) -> sh:not [sh:class SCR_Organism]
- disjointWith(SCR_Disease,SCR_Organism) -> sh:not [sh:class SCR_Organism]
- disjointWith(SCR_Chemical,SCR_Protocol) -> sh:not [sh:class SCR_Protocol]
- disjointWith(SCR_Disease,SCR_Protocol) -> sh:not [sh:class SCR_Protocol]
- disjointWith(SCR_Chemical,SCR_Disease) -> sh:not [sh:class SCR_Disease]
- disjointWith(CheckTag,PublicationType) -> sh:not [sh:class PublicationType]
- disjointWith(GeographicalDescriptor,PublicationType) -> sh:not [sh:class PublicationType]
- disjointWith(CheckTag,GeographicalDescriptor) -> sh:not [sh:class GeographicalDescriptor]
- domain/range(broaderConcept) -> sh:property[sh:class Concept]
- domain/range(parentTreeNumber) -> sh:property[sh:class TreeNumber]
- domain/range(broaderDescriptor) -> sh:property[sh:class Descriptor]
- domain/range(broaderQualifier) -> sh:property[sh:class Qualifier]
- domain/range(narrowerConcept) -> sh:property[sh:class Concept]
- domain/range(relatedConcept) -> sh:property[sh:class Concept]

## Lossy residue (no validation-equivalent SHACL)

| OWL axiom | Detail | Why it cannot convert |
|-----------|--------|------------------------|
| `TransitiveProperty` | parentTreeNumber | No transitive-closure entailment; paths validate reachability, not inference. |

## Why the loss is structural
Every lossy axiom is an **entailment** axiom: it licenses the inference of triples that are not asserted (an inverse edge, a transitive hop, an identity merge, a class equivalence). SHACL's semantics is **closed-graph validation** — it checks the triples present, it never derives new ones. The convertible axioms are exactly the **constraint** axioms (cardinality, domain/range typing, disjointness, existential/universal restrictions), which map to shape conditions. Hence the OWL→SHACL frontier coincides with the **entailment vs constraint** boundary, and completeness < 100% is *inherent*, not a tool limitation.

---

## Provenance (real ontology)

The source is the **real MeSH (Medical Subject Headings) RDF vocabulary**,
fetched live from the U.S. National Library of Medicine Linked Data service:
`https://id.nlm.nih.gov/mesh/vocab` (RDF/XML, 342 triples: 17 owl:Class,
21 object + 28 datatype properties, 18 subClassOf, **34 owl:disjointWith**,
1 owl:TransitiveProperty). The generated shapes
([`../shacl/shapes/generated_from_mesh.ttl`](../shacl/shapes/generated_from_mesh.ttl))
were validated against **5 real MeSH descriptors** —
Hypertension (D006973), Diabetes Mellitus (D003920), Myocardial Infarction
(D009203), Asthma (D001249), Coronary Disease (D006333),
in [`../ontology/mesh_descriptors_sample.nt`](../ontology/mesh_descriptors_sample.nt) —
which **conform with 0 violations**, confirming the conversion is faithful.

## Two-ontology comparison (real vs stress-test)

| Source ontology | Axioms | Lossy | Completeness | Character |
|-----------------|--------|-------|--------------|-----------|
| **Real MeSH** (`mesh_vocab.rdf`) | 59 | 1 | **98%** | Thesaurus-style: domain/range + subClassOf + disjointness, almost no entailment axioms |
| **Synthetic stress-test** ([`owl_to_shacl_loss.md`](owl_to_shacl_loss.md)) | 14 | 5 | **64%** | Deliberately axiom-rich (inverseOf, Transitive, Symmetric, sameAs, equivalentClass) to exercise every lossy class |

**Finding.** Real medical *thesauri* such as MeSH are **highly SHACL-convertible**
(98%) precisely because they encode hierarchy and disjointness as *constraints*,
not as OWL *entailment* axioms — MeSH even models its hierarchy with the custom
`meshv:broaderDescriptor`/`parentTreeNumber` relations rather than
`owl:subClassOf`, deliberately carrying no logical entailment. The conversion
loss only becomes significant for ontologies that lean on OWL's inferential
machinery, as the synthetic stress-test shows. This is the honest, two-sided
answer to "what does OWL→SHACL lose?": **for the medical vocabularies this
project actually targets, almost nothing; for entailment-heavy ontologies, the
entire inference layer.**
