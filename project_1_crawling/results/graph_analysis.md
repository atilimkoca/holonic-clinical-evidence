# Holon-Level Graph Topology Analysis

## Global structure

- Nodes (clinical-question holons): **216**
- Edges (shared disease/drug): **639**, density 0.0275
- Average degree 5.92, max degree 17
- Average clustering coefficient: **1.0**
- Connected components: 43 (largest 18)

## Community detection vs. medical specialty

- Communities detected (greedy modularity): **43** (vs 10 specialties)
- Modularity: **0.9194**
- Purity: **0.8333**, NMI: **0.6827**, ARI: **0.2338**

Interpretation: high purity/NMI means holon clusters (built only from shared diseases/drugs) substantially recover the medical-specialty partition — i.e., topology encodes domain structure.

## Cross-level centrality (structural vs. semantic)

- Spearman(betweenness, aggregate confidence) = **0.0335** (p=0.6249)
- Most divergent holons (structurally central but semantically peripheral, or vice versa): `q_acute_kidney_injury_treatment, q_obsessive_compulsive_disorder_treatment, q_idiopathic_pulmonary_fibrosis_efficacy, q_ankylosing_spondylitis_efficacy, q_irritable_bowel_syndrome_safety`

This extends the midterm 'structurally vs semantically central' question: a weak/insignificant correlation means a holon's bridging role in the graph is largely independent of its evidence strength.

## Holon homomorphism — pattern matches

| Pattern | features | #holons |
|---------|----------|---------|
| `P1_high_conf_treatment` | facet:treatment, high-confidence, relation:treats | 36 |
| `P2_effective_with_1A` | effective, evidence:Level-1A, relation:treats | 28 |
| `P3_side_effect` | facet:safety, relation:causesSideEffect | 68 |
| `P4_cardiology_treatment` | relation:treats, specialty:Cardiology | 20 |

## Subsumption pairs (H_specific ⊑ H_general)

**Pair 1:** `q_atrial_fibrillation_treatment` ⊑ `q_deep_vein_thrombosis_treatment`
- homomorphism φ maps the general projection signature {class:DOAC, effective, evidence:Level-1B, facet:treatment, relation:treats, specialty:Cardiology} into the specific holon;
- extra (specialising) features in the specific holon: {high-confidence}

**Pair 2:** `q_angina_pectoris_treatment` ⊑ `q_cardiomyopathy_treatment`
- homomorphism φ maps the general projection signature {class:Beta blocker, effective, evidence:Level-1B, facet:treatment, relation:treats, specialty:Cardiology} into the specific holon;
- extra (specialising) features in the specific holon: {high-confidence}
