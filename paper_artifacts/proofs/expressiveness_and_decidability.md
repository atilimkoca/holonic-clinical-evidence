# Constraint Recoverability, Access, and Validation Scope

Formal companion to the validation experiment (RQ2). The empirical comparison
uses Set A (boundary-aware holonic constraints), Set B (assertion-scoped rules)
and Set C (context-aware `sh:sparql` over a flat merged export). Set A and Set C
both attain recall 1.00; Set B attains recall 0.52 because its authored rules do
not reconstruct T4--T6. The formal interpretation must therefore distinguish
information availability, constraint-language expressivity, and architectural
accessibility/reuse.

## 1. Formal setting

Let `Sigma` be a finite system of holons and `obs_V(Sigma)` the RDF dataset
available to validator `V` under its access policy. A contextual condition
`phi` is a Boolean property of `Sigma`; a validator can decide `phi` only from
the terms present in, or validly derivable from, `obs_V(Sigma)`.

For T4--T6, the required operands are:

- T4: assertion confidence/effectiveness, owning-holon membership and the
  applicable evidence-quality threshold;
- T5: the relevant drug--disease verdicts and holon memberships needed to compare
  assertions across holons;
- T6: the projection summary and the corresponding interior confidences.

These operands are ordinary RDF terms. Explicit holonic structures make their
scope and role directly addressable; a flat representation may retain or
reconstruct the same bindings and evaluate them through SHACL-SPARQL.

## 2. Proposition -- Constraint Recoverability under Equivalent Access

> **Proposition 1.** For the contextual validation conditions evaluated in
> T4--T6, suppose two validators receive datasets containing the operands and
> policy parameters required by a condition, with a correspondence preserving
> assertion identity, holon membership, relevant verdicts, thresholds and
> projection summaries. Equivalent detection can be implemented either by
> constraints reading explicit holonic boundary structures or by context-aware
> SHACL-SPARQL over a flat merged representation.

**Argument.** Each evaluated condition is a finite query over the bindings
listed above. Under the correspondence, replace each boundary/layer access in
the holonic rule with joins over the retained flat membership and policy terms.
The resulting `sh:sparql` constraint computes the same violating bindings. Set C
is the constructive empirical instance: T4 supplies the evaluated policy's
fixed threshold 0.50, T5 groups assertions by retained membership, and T6
compares retained summaries with member confidences. It reaches the same
observed recall as Set A. This demonstrates recoverability for the evaluated
checks and policy; because C does not retain arbitrary per-holon thresholds, it
does not prove policy-preserving equivalence for every possible holon. QED.

The proposition concerns constraint-language expressivity under equivalent
access. It does not establish equality of arbitrary RDF datasets, identical
authoring effort, fewer joins, lower runtime, greater portability or easier
maintenance.

## 3. Corollary -- Access Limitation

> **Corollary 2.** If a decisive operand or policy parameter is not exposed to a
> validator and is not derivable from its visible dataset, the validator cannot
> in general recover the corresponding contextual condition solely from that
> visible dataset.

**Argument.** Construct two systems whose visible datasets are identical but
whose hidden operand differs so that `phi` is true in one system and false in
the other. Any deterministic validator receives identical inputs and therefore
returns the same result for both, so it must be wrong for at least one. A
randomised validator likewise has the same output distribution on both visible
inputs and cannot guarantee correctness on each. QED.

For T5, the hidden operand may be an opposite verdict in a foreign interior. If
the verdict is not exposed by a projection or an authorised joint view, neither
a flat nor a holonic validator can decide the cross-holon contradiction from the
same incomplete view. T4 and T6 require only the relevant local layers when
those layers are visible. Encapsulation changes the validator's information; it
does not create a stronger RDF or SHACL language.

## 4. Three levels of comparison

1. **Information availability/equivalence.** Are the required evidence and
   policy terms present in the validator's view? RQ1 proves equality only for
   the specified normalised core facts and canonical assertions. Set C omits
   per-holon thresholds, so no broader information-equivalence claim follows.
2. **Constraint-language expressivity.** Can the rule be formulated over the
   available terms? Proposition 1 and Set C show that the evaluated T4--T6
   checks can be expressed in flat RDF with SHACL-SPARQL under merged access and
   the supplied policy parameter.
3. **Architectural accessibility and reuse.** Is admissibility scope explicit,
   local and reusable across components, or reconstructed independently? The
   holonic contribution primarily concerns this level. The same boundary is
   used for validation, querying, retrieval, generation, projection, temporal
   evidence management and governance.

The experiments illustrate level-3 reuse but do not quantitatively establish
lower authoring effort, better maintainability, auditability, portability,
runtime or scalability relative to an equally integrated flat implementation.

## 5. Architectural implication

The boundary is a first-class declaration of evidence-admissibility scope. It
specifies which assertions, policy values and projections belong to a clinical
question and provides a shared address for multiple processing stages. This is
an architectural contribution even though the individual T4--T6 checks remain
recoverable in conventional RDF/SHACL when the same operands are available.
The systems are therefore not identical in organisation or operational access,
but the A--B detection gap is not evidence of exclusive RDF/SHACL expressivity.

## 6. Finite-graph validation scope

For the evaluated finite data graphs, finite shapes graphs, acyclic shape
references and terminating local SPARQL queries, validation terminates by
enumerating finitely many focus/value bindings. This is a termination statement
for the supplied validation task, not a general complexity bound or a claim
about satisfiability under unrestricted entailment. Cyclic shape references
require an explicitly selected recursive semantics. Holon nesting alone does
not establish undecidability or a strict language separation.

## 7. Summary

- Set C constructs equivalent detection for T4--T6 under merged access and the
  evaluated policy.
- Missing operands create an information-access limitation for any validator.
- Explicit boundaries organise and govern scope; they do not manufacture hidden
  information or add exclusive SHACL/RDF expressivity.
- The supported contribution is explicit, reusable admissibility scope across
  the knowledge-to-generation pipeline.

