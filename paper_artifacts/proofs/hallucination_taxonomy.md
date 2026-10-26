# Hallucination Taxonomy and Conditional Grounding Result

Formal companion to the hallucination measurement reported for RQ3. This note
separates admissible evidence, retrieved context and generated assertions so
that retrieval control is not mistaken for a guarantee about a general LLM.

## 1. Grounding model

Fix a question holon `q`. Let `G(q)` be the assertions supported by evidence
admissible for `q` under the evaluated grounding policy. Let
`K = UNION_h G(h)` be the corpus-supported assertion set. An assertion is written
as `(p,e)`, where `p` is a drug--disease pair and `e` is an effectiveness verdict,
possibly omitted. Let `R(q)` be the assertions represented in the retrieved
context and `A(O)` the assertions extracted from output `O`.

Corpus support is not a claim of clinical truth outside the benchmark. A pair
attested elsewhere in `K` may be inappropriate for `q`, and absence from `K`
may reflect corpus incompleteness rather than falsehood in the wider literature.

## 2. Operational taxonomy

For `a=(p,e)` in `A(O)`:

> **Grounded.** `p` is locally supported in `G(q)` and `e` is either omitted or
> agrees with the applicable local verdict. A bare relation supports the pair,
> not an effectiveness verdict.

> **Type A -- corpus-attested but outside the target evidence.** `p` is absent
> from `pairs(G(q))` but present in `pairs(K)`. This is a boundary-grounding or
> context-leakage error, not proof that the assertion is clinically true.

> **Type B -- absent from the corpus grounding set.** `p` is absent from
> `pairs(K)`. The label is corpus-relative and does not establish falsehood in
> the wider literature.

> **Type C -- contradictory verdict.** The pair is attested, but the explicit
> verdict contradicts the applicable reference under the declared conflict and
> tie policy.

The operational precedence is grounded, then C, then A, then B, so each
ungrounded assertion receives at most one label.

For nonempty `A(O)`, the grounding-error rate is

```
HR(O,q) = |{a in A(O) : a is not grounded for q}| / |A(O)|.
```

This equals the sum of Type A/B/C counts divided by `|A(O)|` when every
ungrounded assertion is assigned exactly one category. Empty or unparsable
outputs require a separately declared handling rule and are not evidence of a
grounded answer. Pair-level information coverage is

```
|pairs(A(O)) intersect pairs(G(q))| / |pairs(G(q))|
```

when the denominator is nonempty; coverage does not validate emitted verdicts.

## 3. Retrieval is not generation

For System A, the implemented boundary policy is intended to support

```
R_A(q) subseteq G(q).
```

This inclusion constrains evidential exposure. It does **not** imply

```
A(O_A) subseteq R_A(q)
```

for a general LLM. A model may add assertions through parametric knowledge,
inference, schema completion or semantic over-generation. Boundary-aware
retrieval therefore does not logically imply `HR(O_A,q)=0`.

> **Proposition 1 (Conditional zero-error result).** Assume both
> `R_A(q) subseteq G(q)` and the faithful-transducer condition
> `A(O_A) subseteq R_A(q)`. Then, for a nonempty output,
> `A(O_A) subseteq G(q)` and `HR(O_A,q)=0`.

**Proof.** Transitivity of set inclusion gives
`A(O_A) subseteq R_A(q) subseteq G(q)`. Every emitted assertion is therefore
grounded under the operational reference, so the numerator of `HR` is zero.
QED.

The faithful-transducer condition is an additional generator assumption, not a
property of boundary-aware retrieval or SHACL conformance.

## 4. Deterministic provider and real models

The deterministic provider is deliberately specified to render the retrieved
content according to fixed rules. It therefore approximates the
faithful-transducer condition by construction for the controlled mechanism
experiment. The measured change from 0.760 to 0.000 should be interpreted as a
demonstration of the retrieval policy's effect under specified context adherence,
not as an upper bound on or estimate of general LLM behaviour.

For a real LLM, `A(O) not-subseteq R(q)` is possible. The tested
Llama-3.1-8B configuration demonstrates that unsupported semantic expansion can
occur under boundary-aware retrieval; it does not establish prevalence across
Llama models or model families. Retrieval admissibility, SHACL conformance and
assertion-level grounding must therefore be measured separately.

## 5. Two gates plus an independent grounding check

- **Gate 1 -- evidence admissibility:** boundary-aware retrieval controls which
  evidence is exposed to the generator.
- **Gate 2 -- structural admissibility:** SHACL-derived prompting guides output
  structure and post-generation validation checks the selected schema/shape
  constraints.
- **Independent grounding check:** assertion-level comparison determines whether
  emitted claims are supported by admissible evidence.

Passing Gate 1 does not ensure structural conformance. Passing Gate 2 does not
establish evidential grounding. Passing both does not mathematically prevent a
general LLM from adding unsupported assertions.

## 6. Annotation stability

The final internal stability check compares rule-based labels with a deliberately
perturbed second automated pass over 110 generated assertions and reports
`kappa = 0.78`. This is not human inter-annotator agreement and not a human gold
standard. It measures stability of the automated grounding procedure under the
declared perturbation. Independent human annotation remains future work.

