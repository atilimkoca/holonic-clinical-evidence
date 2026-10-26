# Holon-Level Homomorphism and Subsumption

Formalises the holon-level pattern matching and subsumption required by
assignment §1.4 ("≥ 4 holon-level patterns, 2 subsumption pairs"). The
definitions are realised in [`src/graph_analysis.py`](../src/graph_analysis.py)
and the worked results are in
[`results/graph_metrics.json`](../results/graph_metrics.json).

## 1. Holon signature

For a holon `h` we read a finite **signature** `sig(h) ⊆ Σ` from its
projection/interior content — a set of structural features over the alphabet `Σ`
of facets, specialties, evidence levels, relations, drug classes, and quality
flags:

```
sig(h) = { facet:⟨f⟩, specialty:⟨s⟩, evidence:⟨ℓ⟩ }
       ∪ { relation:⟨r⟩ | h asserts relation r }
       ∪ { class:⟨c⟩ | h's drug has class c }
       ∪ { high-confidence | conf(h) ≥ 0.9 }
       ∪ { effective | effectiveness(h)=effective }
```

This is the abstraction of the holon's *projection graph* `G_prj(h)` into a
property set; two holons with the same signature are projection-indistinguishable.

## 2. Holon homomorphism

> **Definition (pattern homomorphism).** A *pattern* is a feature set `P ⊆ Σ`. A
> holon `h` *matches* `P` (written `P ⤳ h`) iff there is a homomorphism of `P`
> into `sig(h)`, which for property sets is simply `P ⊆ sig(h)`.

This is the holon-level analogue of subgraph homomorphism: the pattern's required
features must all be realised in the holon's signature.

**The four benchmark patterns** (`graph_analysis.PATTERNS`) and their match
counts over the 216-holon corpus:

| Pattern | Features `P` | #matches |
|---------|--------------|----------|
| `P1_high_conf_treatment` | `{facet:treatment, relation:treats, high-confidence}` | 36 |
| `P2_effective_with_1A` | `{relation:treats, evidence:Level-1A, effective}` | 28 |
| `P3_side_effect` | `{facet:safety, relation:causesSideEffect}` | 68 |
| `P4_cardiology_treatment` | `{specialty:Cardiology, relation:treats}` | 20 |

(≥ 4 patterns, all with non-empty match sets — requirement met.)

## 3. Holon subsumption

Specialising the framework's definition (`H₁ ⊑ H₂ iff ∃ homomorphism
φ : G_prj(H₂) → G_prj(H₁)`) to signatures:

> **Definition (subsumption).** `H_specific ⊑ H_general` iff
> `sig(H_general) ⊊ sig(H_specific)`; the inclusion *is* the homomorphism `φ`
> embedding the general projection into the specific one. The specific holon
> carries everything the general one does, plus extra specialising features.

This is a partial order on holons (reflexive, antisymmetric, transitive — it is
exactly set inclusion on signatures).

**Worked pairs** (`graph_analysis.find_subsumptions`, verified computationally):

**Pair 1 — `q_atrial_fibrillation_treatment ⊑ q_deep_vein_thrombosis_treatment`.**
`φ` embeds the general signature
`{facet:treatment, relation:treats, specialty:Cardiology, class:DOAC,
evidence:Level-1B, effective}` into the AF-treatment holon, which additionally
satisfies `high-confidence`. Reading: both are Level-1B DOAC cardiology treatment
holons; the AF holon is the *more specific* one (higher-confidence evidence), so
it subsumes (is below, in the ⊑ order) the DVT holon.

**Pair 2 — `q_angina_pectoris_treatment ⊑ q_cardiomyopathy_treatment`.**
`φ` embeds `{facet:treatment, relation:treats, specialty:Cardiology,
class:Beta blocker, evidence:Level-1B, effective}`; the angina holon adds
`high-confidence`.

Both pairs satisfy the antisymmetry check (signatures differ) and the inclusion
is strict, so the homomorphism is a proper embedding.

## 4. Relation to graph topology

The signature lattice complements the holon-level co-occurrence graph
(`graph_analysis`): subsumption groups holons by *projection content*, while
community detection groups them by *shared entities*. Both independently recover
medical structure — communities are specialty-pure (purity 0.83, NMI 0.68) and
subsumption chains stay within a specialty/drug-class — corroborating that the
holonic topology encodes domain semantics.
