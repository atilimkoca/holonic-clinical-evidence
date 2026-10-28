# `Transform(S)`: Formal Definition, Correctness, and Convergence

Formal companion to the SHACL-guided generation pipeline. This note gives
the formal object behind the shape-to-prompt transformation: the map `Transform`
from a SHACL shape to an LLM prompt template, the precise sense in which it is
*correct*, and a convergence analysis of the iterative-repair loop.

Notation: a SHACL shapes graph `S`, an RDF
graph `O` produced by the model, `O |= S` for SHACL-conformance, and a holon
`H = <G_int, G_bnd, G_prj, G_ctx>`.

---

## 1. The transformation

### 1.1 Shape as a constraint tuple

A SHACL node shape `s in S` with target class `C` is, after parsing, a finite
set of property constraints

```
s = <C, {pi_1, ..., pi_m}>,   pi_j = (path_j, tau_j, kappa_j, iota_j, rho_j, sigma_j)
```

where for property `j`: `path_j` is the predicate, `tau_j` the datatype/class,
`kappa_j = (min_j, max_j)` the cardinality, `iota_j` the value enumeration (`sh:in`),
`rho_j` the range/pattern facets (`sh:minInclusive`, `sh:maxInclusive`,
`sh:pattern`), and `sigma_j in {Info, Warning, Violation}` the severity. This is
exactly the `ShapeTemplate` / `PropertyConstraint` dataclass pair produced by
`transform(g, shape_uri)`.

Define the **required set**

```
Req(s) = { path_j : sigma_j = Violation /\ min_j >= 1 }.
```

A field's omission is *rejected* (a Violation) iff its path is in `Req(s)`;
`shacl_to_prompt.PropertyConstraint.required` computes exactly this predicate.
For `oe:EvidenceReifierShape`, `Req = {holon:confidence, holon:evidenceLevel,
oe:cites}` (verified by the runnable CLI).

### 1.2 Definition (Transform)

> **Definition 1 (Transform).** `Transform` is the computable map
> `Transform(s, x) = (h || R(s) || K(s, x) || T(s))` where, given a shape `s` and a
> grounded-evidence context `x`:
> - `h` is a fixed instruction header forbidding ungrounded content;
> - `R(s)` is the rendering of `Req(s)` as imperative "REQUIRED" lines, each
>   carrying its datatype, range, enumeration and cardinality facets;
> - `K(s, x)` renders the recommended fields and the grounded facts of `x`;
> - `T(s)` is the fill-in skeleton (`subject a C ; path_j <<placeholder_j>> ...`).
>
> `Transform` is total and deterministic: it is a structural fold over the
> finite constraint tuple of `s`, so it always terminates and depends only on
> `(s, x)`. (`render_prompt` is a pure function of `ShapeTemplate`.)

The naive baseline prompt `Naive(x)` ships the same grounded context `x` but
omits `R(s)`, `T(s)` and `h`'s structural clauses -- i.e. it carries **no shape
information**. This is the only difference the experiment manipulates.

---

## 2. Correctness

Let `M` be a fixed model (temperature 0) inducing, for a prompt `p`, a
distribution `Pr[O = * | p]` over outputs. Write

```
gamma(p) = Pr[ O |= s | p ]      (the conformance probability of prompt p).
```

> **Definition 2 (Transform-correctness).** `Transform` is *correct for `(M, s)`
> on a context family `X`* iff
> ```
> gamma(Transform(s, x)) > gamma(Naive(x))      for all x in X.
> ```

### 2.1 Why the inequality should hold (information argument)

Conformance `O |= s` is the conjunction of per-constraint events
`A_j = "O satisfies pi_j"`. For a Violation field `j`, `A_j` requires the model to
(i) *emit* `path_j` with the right cardinality and (ii) emit a value in the
admissible set `V_j = iota_j inter tau_j inter rho_j`.

`Transform(s, x)` states `path_j`, `V_j` and `kappa_j` **explicitly** in `R(s)` and
pins their surface form in `T(s)`; `Naive(x)` leaves the model to *infer* the
required predicates and admissible values from raw triples. Under any model
whose emission probability for a field is monotone in the explicitness of the
instruction (the standard "instruction-following" assumption),

```
Pr[A_j | Transform] >= Pr[A_j | Naive]   for every j, with strict '>' for at
least one Violation field whenever Req(s) not subseteq surface(x).
```

Conformance is the conjunction `AND_j A_j`; the per-constraint domination plus one
strict gain gives `gamma(Transform) > gamma(Naive)`, i.e. Definition 2. The experiment
reported in Sec. 6.3 of the article is the empirical test of this inequality:
**first-pass conformance** is the Monte-Carlo estimate of `gamma(*)` over the
100-question set.

> **Caveat (honest).** The argument is conditional on instruction-following
> monotonicity; it is *not* an unconditional theorem about arbitrary `M`. A model
> that ignores instructions, or a context `x` that already spells out every
> required field, collapses the gap. We therefore *measure* the effect rather
> than assert it, and report the deterministic-versus-real-provider distinction
> among the limitations in Sec. 8 of the article. The default deterministic mock satisfies the monotonicity
> assumption **by construction** (it emits `Req(s)` when `Req(s)` is supplied and
> omits holon-layer scaffolding otherwise), so it is a controlled witness of
> the prompt mechanism rather than an estimate of real-model behaviour.

---

## 3. The iterative-repair loop and its convergence

The generator runs the loop (max `k` iterations):

```
p_0 = Transform(s, x)
for t = 0 ... k-1:
    O_t = M(p_t)
    if O_t |= s: return (O_t, pass at t)
    V_t = violations(O_t, s)              # pySHACL validation report
    p_{t+1} = p_t (+) Repair(V_t)           # append the failed paths + messages
return (O_{k-1}, fail)
```

`Repair(V_t)` extracts the focus paths and messages of the firing Violation
results and appends them as additional REQUIRED lines (`repair_fields`), so each
iteration strictly increases the explicit constraint information given to `M`.

### 3.1 Convergence claim

> **Proposition 1 (monotone conformance under idealised repair).** Assume (a)
> each violated field, once named in `Repair`, is satisfied on the next
> iteration with probability >= q > 0 and never regresses (a satisfied field
> stays satisfied because its value is pinned in the prompt), and (b) the number
> of required fields `|Req(s)|` is finite. Then the per-iteration conformance
> probability `c_t = Pr[O_t |= s]` is non-decreasing, and the probability of
> non-conformance after `k` rounds is bounded by
> ```
> Pr[O_k |/= s] <= |Req(s)| * (1 - q)^{k}.
> ```
> Hence `c_t -> 1` geometrically; with `|Req| = 3` and `q ~= 0.7`, `k = 3` gives a
> residual <= 3*0.027 ~= 0.08.

*Proof sketch.* By (a) each of the <= `|Req(s)|` initially-violated fields fails
to be repaired across `k` independent rounds with probability <= `(1-q)^k`; a
union bound over the fields gives the stated bound, and "no regression" makes
`c_t` monotone. QED

The **non-regression** hypothesis is an explicit condition of the bound, not a
property enforced by prompt accumulation or temperature zero. Restating pinned
values may encourage preservation, but a model can ignore the repair, alter a
previously valid field or add a new invalid node. This is why the manuscript
reports both **first-pass** and **converged (k=3)** conformance as finite-budget
empirical outcomes rather than claiming guaranteed geometric convergence.

### 3.2 What convergence does *not* buy

Conformance is *structural*. `O_k |= s` guarantees the shape's constraints hold,
**not** that the content is faithful to the sources -- that is the separate
hallucination axis (Type A/B/C, see
`hallucination_taxonomy.md`). A model can converge
to a SHACL-valid graph that still asserts an ungrounded `oe:treats` edge. The
boundary-aware System A attacks *that* axis with confidence-filtered,
projection-only context; the SHACL loop attacks only the structural axis. The
two are complementary, which is exactly why RQ_3 measures both.
