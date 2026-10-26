# §2.7 — Governance-Dependent Validation (Project 2's contribution to RQ₄)

How does SHACL validation change under the three governance topologies, and
which one best balances **cross-holon detection** against **cost**? This is the
validation-layer half of **RQ₄**; Projects 1 and 3 contribute the storage and
LLM halves.

Run: `../../.venv/bin/python src/governance_validation.py`
→ writes [`../results/governance.csv`](../results/governance.csv).

---

## 1. The three regimes as *validation scopes*

The governance topology **is** the validator's access model (Theorem 2, §2.5):

| Regime | Validator input | Authority `A` (Def. 4) | Access `R` (Def. 4) |
|--------|-----------------|------------------------|---------------------|
| **C1 Centralized** | union of all holon interiors | `centralized` | `full-access` |
| **C2 Federated** | each interior + peers' **projections** | `federated` | `boundary-negotiated` |
| **C3 Autonomous** | each holon's **own interior only** | `autonomous` | `projection-only` |

The cross-holon contradiction `φ_T5` is detectable iff the regime's scope makes
both sides visible — either both interiors (C1) or one interior + the peer's
surfaced projection (C2). C3 sees neither and is blind.

## 2. Results — detection + scalability (N = 50 … 1000)

Run at the assignment-mandated scales (`results/governance.csv`):

| N | Centralized det / latency | Federated det / latency | Autonomous det / latency |
|------|---------------------------|--------------------------|---------------------------|
| 50 | 100% / 0.84 s | 100% / 0.06 s | 0% / 0.05 s |
| 100 | 100% / 3.47 s | 100% / 0.13 s | 0% / 0.12 s |
| 200 | 100% / **22.0 s** | 100% / **0.36 s** | 0% / 0.23 s |
| 500 | **impractical (O(N²))** | 100% / 1.65 s | 0% / 0.55 s |
| 1000 | **impractical (O(N²))** | 100% / **5.99 s** | 0% / 1.11 s |

(detection_rate = detected / gold cross-holon contradictions. Centralized was
capped at N≤200: its O(N²) cross-holon scan over one monolithic union becomes
impractical beyond that — which is itself the scalability finding.)

**Three findings:**

1. **Detection.** Centralized and Federated both reach **100%**; Autonomous
   reaches **0%** at every scale. Cross-holon consistency is *impossible* under
   pure autonomy unless verdicts are surfaced into projections — exactly what
   the federated boundary obligation does.

2. **Cost / scalability.** Centralized latency grows **super-linearly** —
   0.84 → 3.47 → 22.0 s as N goes 50 → 100 → 200 (a ~6× jump per doubling,
   ≈ `O(N²)`), because the cross-holon SPARQL matches every "effective"
   assertion against *all* "ineffective" ones over one union graph. It is
   already **61× slower than Federated at N=200** (22.0 s vs 0.36 s) for the
   *same* 100% detection, and impractical by N=500.

3. **Federated scales.** Federation bounds each check to one interior against
   the shared projection set, reaching **N=1000 in 6 s with full detection** —
   near-linear growth. It is the only regime that keeps both 100% detection
   *and* tractable cost at scale.

## 3. The governance trade-off, quantified

| Property | Centralized | Federated | Autonomous |
|----------|-------------|-----------|------------|
| Cross-holon detection | ✅ 100% | ✅ 100% | ❌ 0% |
| Validation latency (N=80) | 1.98 s | 0.10 s | 0.08 s |
| Scaling | super-linear (O(N²)) | near-linear | linear |
| Single point of failure | yes | no | no |
| Schema-evolution cost | O(\|S\|·\|H\|) (all holons) | committee / shared boundary | local |
| Privacy (interior exposure) | full exposure | projections only | none |

This instantiates **Proposition 5** (the governance ⇄ interoperability
trade-off): centralized guarantees semantic interoperability trivially but pays
`O(\|S\|·\|H\|)` on every schema change and exposes all interiors; autonomous is
cheap and private but forfeits global consistency; **federated is the knee of
the curve** — it recovers full cross-holon detection at near-autonomous latency
by paying only the cost of *projection plumbing* (each holon publishes its
verdict to a shared boundary).

## 4. Domain-dependent recommendation (medical evidence)

The "best" topology is **domain-dependent** (the assignment's core claim), and
the medical-evidence domain is **heterogeneous**, so a single topology is
sub-optimal. Mapping our finding onto medical sub-domains:

| Medical sub-domain | Characteristics | Recommended regime |
|--------------------|-----------------|--------------------|
| **Drug–drug interactions** | safety-critical, contradiction = harm | **Centralized** — pay the O(N²) cost; a missed cross-holon contradiction is unacceptable |
| **General disease Q&A** | high volume, low risk, frequently updated | **Autonomous** — cheap, parallel, evolvable; cross-holon coherence not critical |
| **Guideline / evidence synthesis** | cross-source contradictions matter but volume manageable | **Federated** — surface verdicts to a shared boundary; full detection at low cost |

→ **Hybrid recommendation (formal, in GT(S) notation):**
```
GT(S_medical) = ⟨A, V, R⟩ with
  A(h) = centralized   if h ∈ DrugInteractionHolons
       = federated     if h ∈ EvidenceSynthesisHolons
       = autonomous     if h ∈ GeneralQAHolons
  V(h) = global        for centralized h ;  local+boundary for federated h ;  self for autonomous h
  R(h) = full-access for centralized ; boundary-negotiated for federated ; projection-only for autonomous
```

This matches the **Data Mesh** philosophy (domain-owned, federated governance,
Dehghani 2022) for the bulk, with **centralized islands** for safety-critical
sub-graphs — closer to GAIA-X/IDS *polycentric* governance than to either pure
SOLID autonomy or a Google-KG-style monolith. The decisive variable is
**cost-of-a-missed-contradiction**: where it is high (drug safety), centralize;
where it is low (general Q&A), autonomise; in between, federate with projection
surfacing.

## 5. Link back to the experiment and Theorem 2

The §2.4 corpus experiment ran under an implicit **C1 (centralized)** scope —
each corpus file is one merged graph — which is why Set A reaches 100% recall on
T5/T6 there. This §2.7 experiment shows that **the same shapes lose that recall
the moment the scope shrinks to autonomy**, and recover it under federation only
because the projection-surfacing obligation re-admits the evidence. Detection is
therefore a property of **shapes × governance scope**, not shapes alone — the
central practical lesson Project 2 contributes to the integrated RQ₄ study.
