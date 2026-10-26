# Information-Preserving Bijection between Model A (Holonic) and Model B (Flat)

This note states and proves the information-preservation property required by
assignment §1.2 ("the two models must represent the same information; an
information-preserving bijection must be shown"). The check is mechanised in
[`src/benchmark.py`](../src/benchmark.py) (`check_information_preservation`) and
its result is in [`results/info_preservation.json`](../results/info_preservation.json).

## 1. Setup

Both models are generated from one normalised fact set by
[`rdf_transformer.py`](../src/rdf_transformer.py):

- **A** — holonic RDF 1.2 dataset; four named graphs per holon; edge metadata via
  the materialised reifier pattern (`holon:EvidenceAssertion` + `rdf:reifies` +
  triple term).
- **B** — flat RDF 1.1 graph; one default graph; edge metadata via
  `rdf:Statement`.

## 2. The predicate→layer map λ

The only structure present in A but not as data in B is the **layer partition**.
It is captured by a total function

```
λ : Predicate → {interior, boundary, projection, context}
```

defined in `rdf_transformer.LAYER_OF_PREDICATE`, e.g.

| predicate | layer |
|-----------|-------|
| `oe:questionText`, `oe:answerText`, `oe:treats`, `rdf:reifies`, `oe:cites`, `holon:inHolon` | interior |
| `holon:evidenceQualityThreshold`, `holon:entryMode` | boundary |
| `holon:narrativeFunction`, `holon:summaryConfidence`, `holon:aggregateConfidence`, `holon:prerequisiteFor` | projection |
| `prov:wasAttributedTo`, `prov:generatedAtTime`, `prov:wasDerivedFrom`, `holon:recordedOn` | context |

`λ` is well-defined: in our schema each layer-bearing predicate occurs in exactly
one layer.

## 3. The bijection β

Define `β = β₂ ∘ β₁`:

**β₁ (reification idiom).** Bijectively rewrite each edge annotation between the
two encodings:
```
A:  r a holon:EvidenceAssertion ; rdf:reifies t .         t rdf:subject s ; rdf:predicate p ; rdf:object o .   r ⟨meta⟩
B:  r a rdf:Statement ; rdf:subject s ; rdf:predicate p ; rdf:object o .                                       r ⟨meta⟩
```
This is a node-for-node, metadata-preserving rewrite (the reifier IRI `r` and all
`⟨meta⟩` triples are identical on both sides), hence invertible.

**β₂ (graph placement).**
- `A → B`: drop the named-graph boundaries (union all layer graphs into the
  default graph) and drop the `holon:has{Interior,Boundary,Projection,Context}Graph`
  pointers (they only name the now-removed graphs).
- `B → A`: send each triple `τ` to graph `G_{λ(pred(τ))}^{holon(τ)}`, where
  `holon(τ)` is recovered from the subject's `holon:inHolon` (for reifiers) or
  from the holon IRI itself (for holon-subject triples), and re-add the four
  graph pointers.

Both directions are deterministic and mutually inverse ⇒ **β is a bijection.**

## 4. Mechanised check

Rather than reconstruct graphs, the implementation verifies β by comparing two
canonical invariants that β preserves:

1. **CORE** — every triple except reification plumbing and the A-only graph
   pointers. (Identical IRIs ⇒ comparable across models.)
2. **ASRT** — the canonical assertion tuple
   `⟨s, p, o, confidence, evidenceLevel, recordedOn, inHolon, effectiveness, cites⟩`
   read from whichever reification idiom each model uses.

> **Theorem.** β exists **iff** `CORE(A) = CORE(B)` and `ASRT(A) = ASRT(B)`.

**Measured (`results/info_preservation.json`):**

| invariant | A | B | equal |
|-----------|---|---|-------|
| CORE facts | 11329 | 11329 | ✅ |
| canonical assertions | 204 | 204 | ✅ |
| set differences (A\B, B\A) | 0 / 0 | 0 / 0 | ✅ |
| **bijection_holds** | | | **true** |

(Exact counts as emitted by the latest run; CORE excludes the 4·|H| named-graph
pointers, which are structure, not facts — see §3 β₂.)

## 5. Consequence

Because β is a bijection, the two models are *information-equivalent*: neither
loses a fact. The expressiveness difference measured in
[`expressiveness.md`](expressiveness.md) is therefore strictly about
**queryability of the layer partition as data**, not about representable
information — the honest, defensible reading of H₁.
