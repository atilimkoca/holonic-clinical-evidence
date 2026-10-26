"""run_experiment.py — controlled comparison for RQ3 (Project 3, Student C).

Runs the three §3.3 experiments over the 100-question test set, System A
(holon-based, SHACL-guided) vs System B (naive GraphRAG), sharing one LLM,
question set and metric suite:

  Deney 1 — Conformance : first-pass + converged (k=3) SHACL conformance,
            per-iteration convergence curve, McNemar's test (paired binary).
  Deney 2 — Hallucination: Type A/B/C rate per question, paired test
            (Shapiro -> t-test / Wilcoxon), Cohen's d, bootstrap CI.
  Deney 3 — Coverage     : information coverage + precision@k, paired test.
  Plus token efficiency (correct assertions / tokens).

Writes results/{accuracy,hallucination,performance}/*.csv, results/summary.md and
results/figures/*.png. Deterministic on the default mock provider (seed-free:
the pipeline itself is deterministic); a real LLM activates via P3_LLM_PROVIDER.
"""
from __future__ import annotations

import argparse
import csv
import statistics as st
import sys
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt          # noqa: E402
from scipy import stats as sps            # noqa: E402
from statsmodels.stats.contingency_tables import mcnemar  # noqa: E402

_SRC = Path(__file__).resolve().parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
_P2_SRC = _SRC.parents[1] / "project_2_semantic" / "src"
if str(_P2_SRC) not in sys.path:
    sys.path.insert(0, str(_P2_SRC))

from dataset import grounding_graph_for, load_testset            # noqa: E402
from graph_rag import DualRAG                                     # noqa: E402
from evaluation import evaluate_generation                        # noqa: E402
from llm_generator import generate                                # noqa: E402
from llm_provider import get_provider                             # noqa: E402
from shacl_to_prompt import load_shapes as load_shape_templates, node_shapes, transform  # noqa: E402
from shacl_validator import load_ontology, load_shapes           # noqa: E402

_PROJ = _SRC.parent
P2_SHAPES_A = _SRC.parents[1] / "project_2_semantic" / "shacl" / "shapes" / "boundary_aware"
RES = _PROJ / "results"
K = 3


# --------------------------------------------------------------------------- #
# Statistics helpers
# --------------------------------------------------------------------------- #

def mcnemar_binary(a_ok: list, b_ok: list) -> dict:
    """McNemar on paired binary correctness (here: 'conforms')."""
    n00 = sum(1 for a, b in zip(a_ok, b_ok) if a and b)
    n01 = sum(1 for a, b in zip(a_ok, b_ok) if a and not b)
    n10 = sum(1 for a, b in zip(a_ok, b_ok) if not a and b)
    n11 = sum(1 for a, b in zip(a_ok, b_ok) if not a and not b)
    res = mcnemar([[n00, n01], [n10, n11]], exact=True)
    return {"table": [[n00, n01], [n10, n11]],
            "statistic": float(res.statistic), "p": float(res.pvalue)}


def paired_test(a: list, b: list) -> dict:
    """Shapiro on the paired differences -> paired t-test (normal) or Wilcoxon."""
    diffs = [x - y for x, y in zip(a, b)]
    nonzero = [d for d in diffs if d != 0]
    out = {"n": len(diffs), "mean_diff": st.mean(diffs) if diffs else 0.0,
           "n_nonzero": len(nonzero)}
    if len(nonzero) < 3 or len(set(nonzero)) < 2:
        out.update(test="degenerate", statistic=float("nan"), p=float("nan"),
                   normal=False)
        return out
    sh_p = float(sps.shapiro(diffs)[1]) if 3 <= len(diffs) <= 5000 else 0.0
    out["shapiro_p"] = sh_p
    out["normal"] = sh_p > 0.05
    if out["normal"]:
        t, p = sps.ttest_rel(a, b)
        out.update(test="paired t-test", statistic=float(t), p=float(p))
    else:
        try:
            w, p = sps.wilcoxon(a, b)
            out.update(test="Wilcoxon signed-rank", statistic=float(w), p=float(p))
        except ValueError:
            out.update(test="Wilcoxon (degenerate)", statistic=float("nan"),
                       p=float("nan"))
    return out


def cohens_d_paired(a: list, b: list) -> float:
    diffs = [x - y for x, y in zip(a, b)]
    sd = st.pstdev(diffs)
    return (st.mean(diffs) / sd) if sd else 0.0


def bootstrap_ci(values: list, n_boot: int = 2000, seed: int = 42) -> tuple:
    import random
    rng = random.Random(seed)
    n = len(values)
    if n == 0:
        return (0.0, 0.0, 0.0)
    means = []
    for _ in range(n_boot):
        means.append(st.mean(values[rng.randrange(n)] for _ in range(n)))
    means.sort()
    return (st.mean(values), means[int(0.025 * n_boot)], means[int(0.975 * n_boot)])


# --------------------------------------------------------------------------- #
# Experiment driver
# --------------------------------------------------------------------------- #

def run(n=None, k=K, provider=None, questions=None, write_generated=True):
    rag = DualRAG()
    questions = list(questions) if questions is not None else rag.questions
    questions = questions[:n] if n else questions
    provider = provider or get_provider()

    sg = load_shape_templates(P2_SHAPES_A)
    cq = next(s for s in node_shapes(sg) if str(s).endswith("ClinicalQuestionShape"))
    template = transform(sg, cq)
    shapes, ont = load_shapes(P2_SHAPES_A), load_ontology()

    rows = []
    t0 = time.perf_counter()
    for q in questions:
        rec = {"holon_id": q.holon_id, "specialty": q.specialty}
        grounding = grounding_graph_for(q)        # real entities incl. publicationDate
        for sysname in ("A", "B"):
            ctx = rag.context(q, sysname)
            gres = generate(template, ctx.to_generator_context(), system=sysname,
                            provider=provider, grounding=grounding,
                            shapes_graph=shapes, ont_graph=ont, k=k,
                            write=write_generated)
            hrep = evaluate_generation(gres.output_ttl, q, sysname)
            cum = _cumulative(gres.per_iter_conforms, k)
            rec[sysname] = {
                "first_pass": gres.first_pass, "converged": gres.passed,
                "iters": gres.iterations, "cum_conform": cum,
                "hr": hrep.hallucination_rate, "coverage": hrep.coverage,
                "p_at_1": hrep.precision_at_1, "p_at_3": hrep.precision_at_3,
                "grounded": hrep.grounded, "a": hrep.type_a, "b": hrep.type_b,
                "c": hrep.type_c, "ctx_tokens": ctx.context_tokens,
                "gen_tokens": gres.total_tokens,
                "tok_eff": hrep.grounded / gres.total_tokens if gres.total_tokens else 0.0,
            }
        rows.append(rec)
    elapsed = time.perf_counter() - t0
    _write_all(rows, k, elapsed, provider)
    return rows


def _cumulative(per_iter: list, k: int) -> list:
    """cum[t] = conformed by iteration t (0-indexed), padded to length k."""
    cum, seen = [], False
    for t in range(k):
        if t < len(per_iter) and per_iter[t]:
            seen = True
        cum.append(seen)
    return cum


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #

def _rate(rows, sysname, key):
    return [1.0 if r[sysname][key] else 0.0 for r in rows]


def _vals(rows, sysname, key):
    return [r[sysname][key] for r in rows]


def _write_all(rows, k, elapsed, provider):
    for sub in ("accuracy", "hallucination", "performance", "figures"):
        (RES / sub).mkdir(parents=True, exist_ok=True)

    # ---- per-question CSVs ------------------------------------------------- #
    with (RES / "accuracy" / "conformance.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["holon_id", "fp_A", "fp_B", "conv_A", "conv_B",
                    "iters_A", "iters_B"])
        for r in rows:
            w.writerow([r["holon_id"], r["A"]["first_pass"], r["B"]["first_pass"],
                        r["A"]["converged"], r["B"]["converged"],
                        r["A"]["iters"], r["B"]["iters"]])
    with (RES / "hallucination" / "hallucination.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["holon_id", "hr_A", "hr_B", "covA", "covB", "p3A", "p3B",
                    "A_typeA", "A_typeB", "A_typeC", "B_typeA", "B_typeB", "B_typeC"])
        for r in rows:
            w.writerow([r["holon_id"], f"{r['A']['hr']:.3f}", f"{r['B']['hr']:.3f}",
                        f"{r['A']['coverage']:.2f}", f"{r['B']['coverage']:.2f}",
                        f"{r['A']['p_at_3']:.2f}", f"{r['B']['p_at_3']:.2f}",
                        r["A"]["a"], r["A"]["b"], r["A"]["c"],
                        r["B"]["a"], r["B"]["b"], r["B"]["c"]])
    with (RES / "performance" / "efficiency.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["holon_id", "ctxTok_A", "ctxTok_B", "genTok_A", "genTok_B",
                    "tokEff_A", "tokEff_B"])
        for r in rows:
            w.writerow([r["holon_id"], r["A"]["ctx_tokens"], r["B"]["ctx_tokens"],
                        r["A"]["gen_tokens"], r["B"]["gen_tokens"],
                        f"{r['A']['tok_eff']:.5f}", f"{r['B']['tok_eff']:.5f}"])

    # ---- statistics -------------------------------------------------------- #
    fp_mc = mcnemar_binary(_rate_bool(rows, "A", "first_pass"),
                           _rate_bool(rows, "B", "first_pass"))
    cv_mc = mcnemar_binary(_rate_bool(rows, "A", "converged"),
                           _rate_bool(rows, "B", "converged"))
    hr_A, hr_B = _vals(rows, "A", "hr"), _vals(rows, "B", "hr")
    cov_A, cov_B = _vals(rows, "A", "coverage"), _vals(rows, "B", "coverage")
    eff_A, eff_B = _vals(rows, "A", "tok_eff"), _vals(rows, "B", "tok_eff")
    hr_test = paired_test(hr_B, hr_A)            # B - A (expect B higher)
    hr_d = cohens_d_paired(hr_B, hr_A)
    cov_test = paired_test(cov_A, cov_B)
    eff_test = paired_test(eff_A, eff_B)
    ci_A = bootstrap_ci(hr_A); ci_B = bootstrap_ci(hr_B)

    stats = {"fp_mcnemar": fp_mc, "cv_mcnemar": cv_mc, "hr_test": hr_test,
             "hr_cohens_d": hr_d, "cov_test": cov_test, "eff_test": eff_test,
             "ci_A": ci_A, "ci_B": ci_B}
    _write_summary(rows, k, elapsed, provider, stats)
    _figures(rows, k)
    _print_headline(rows, stats, provider)


def _rate_bool(rows, sysname, key):
    return [bool(r[sysname][key]) for r in rows]


def _conv_curve(rows, sysname, k):
    n = len(rows)
    return [sum(1 for r in rows if r[sysname]["cum_conform"][t]) / n for t in range(k)]


def _write_summary(rows, k, elapsed, provider, S):
    n = len(rows)
    fp_A = st.mean(_rate(rows, "A", "first_pass"))
    fp_B = st.mean(_rate(rows, "B", "first_pass"))
    cv_A = st.mean(_rate(rows, "A", "converged"))
    cv_B = st.mean(_rate(rows, "B", "converged"))
    hr_A = st.mean(_vals(rows, "A", "hr")); hr_B = st.mean(_vals(rows, "B", "hr"))
    cov_A = st.mean(_vals(rows, "A", "coverage")); cov_B = st.mean(_vals(rows, "B", "coverage"))
    eff_A = st.mean(_vals(rows, "A", "tok_eff")); eff_B = st.mean(_vals(rows, "B", "tok_eff"))
    md = []
    md.append("# RQ3 — Holon-Based vs Naive GraphRAG: Controlled Comparison\n")
    md.append(f"- Questions: **{n}**  ·  k = {k}  ·  LLM provider: "
              f"**{provider.name}** ({provider.model})  ·  wall-clock {elapsed:.1f}s\n")

    md.append("\n## Deney 1 — SHACL Conformance\n")
    md.append("| Metric | System A | System B |")
    md.append("|--------|----------|----------|")
    md.append(f"| First-pass conformance | **{fp_A:.0%}** | {fp_B:.0%} |")
    md.append(f"| Converged conformance (k={k}) | **{cv_A:.0%}** | {cv_B:.0%} |")
    fp, cv = S["fp_mcnemar"], S["cv_mcnemar"]
    md.append(f"\nMcNemar (first-pass): discordant A>B={fp['table'][0][1]}, "
              f"B>A={fp['table'][1][0]}, p = **{fp['p']:.3e}** "
              f"-> {'REJECT H0' if fp['p'] < 0.05 else 'fail to reject H0'}.")
    md.append(f"\nMcNemar (converged): discordant A>B={cv['table'][0][1]}, "
              f"B>A={cv['table'][1][0]}, p = **{cv['p']:.3e}** "
              f"-> {'REJECT H0' if cv['p'] < 0.05 else 'fail to reject H0'}.")
    md.append("\n### Convergence curve (fraction conforming by iteration)\n")
    md.append("| Iteration | System A | System B |")
    md.append("|-----------|----------|----------|")
    ca, cb = _conv_curve(rows, "A", k), _conv_curve(rows, "B", k)
    for t in range(k):
        md.append(f"| {t} | {ca[t]:.0%} | {cb[t]:.0%} |")

    md.append("\n## Deney 2 — Hallucination (Type A/B/C)\n")
    md.append("| Metric | System A | System B |")
    md.append("|--------|----------|----------|")
    md.append(f"| Mean hallucination rate | **{hr_A:.3f}** | {hr_B:.3f} |")
    aA = sum(r["A"]["a"] for r in rows); bA = sum(r["A"]["b"] for r in rows); cA = sum(r["A"]["c"] for r in rows)
    aB = sum(r["B"]["a"] for r in rows); bB = sum(r["B"]["b"] for r in rows); cB = sum(r["B"]["c"] for r in rows)
    md.append(f"| Type A / B / C totals | {aA} / {bA} / {cA} | {aB} / {bB} / {cB} |")
    t = S["hr_test"]
    md.append(f"\nAssumption check: Shapiro p = {t.get('shapiro_p', float('nan')):.3e} "
              f"-> differences {'normal' if t.get('normal') else 'non-normal'}; "
              f"using **{t['test']}**.")
    md.append(f"\n{t['test']} on per-question (B-A): statistic = {t['statistic']:.3f}, "
              f"p = **{t['p']:.3e}**, Cohen's d = **{S['hr_cohens_d']:.2f}** "
              f"-> {'REJECT H0' if (t['p'] == t['p'] and t['p'] < 0.05) else 'fail to reject H0'}.")
    md.append(f"\n95% bootstrap CI on hallucination rate: "
              f"A {S['ci_A'][0]:.3f} [{S['ci_A'][1]:.3f}, {S['ci_A'][2]:.3f}], "
              f"B {S['ci_B'][0]:.3f} [{S['ci_B'][1]:.3f}, {S['ci_B'][2]:.3f}].")

    md.append("\n## Deney 3 — Coverage & Token Efficiency\n")
    md.append("| Metric | System A | System B |")
    md.append("|--------|----------|----------|")
    md.append(f"| Information coverage | {cov_A:.2f} | {cov_B:.2f} |")
    md.append(f"| Token efficiency (grounded/token) | **{eff_A:.4f}** | {eff_B:.4f} |")
    md.append(f"| Mean context tokens | **{st.mean(_vals(rows,'A','ctx_tokens')):.0f}** "
              f"| {st.mean(_vals(rows,'B','ctx_tokens')):.0f} |")
    ct = S["cov_test"]; et = S["eff_test"]
    md.append(f"\nCoverage ({ct['test']}): p = {ct['p']:.3e}. "
              f"Token efficiency ({et['test']}): p = **{et['p']:.3e}**.")

    md.append("\n## Hypothesis verdict (H3)\n")
    if abs(cv_A - cv_B) < 1e-9:
        conv_note = ("converged conformance is equal (both reach the same rate "
                     "under the k=3 repair budget)")
    elif cv_A > cv_B:
        conv_note = (f"converged conformance remains higher for A "
                     f"({cv_A:.0%} vs {cv_B:.0%})")
    else:
        conv_note = (f"converged conformance is lower for A "
                     f"({cv_A:.0%} vs {cv_B:.0%})")
    fp_direction = ("raises" if fp_A > fp_B else
                    "lowers" if fp_A < fp_B else "does not change")
    md.append(f"- **Conformance**: first-pass {fp_A:.0%} (A) vs {fp_B:.0%} (B), "
              f"p={fp['p']:.2e} -> SHACL-guided initialisation {fp_direction} first-pass "
              f"conformance; {conv_note}.")
    hall_change = _safe_drop(hr_B, hr_A)
    hall_desc = (f"a {hall_change:.0%} relative reduction" if hall_change >= 0 else
                 f"a {-hall_change:.0%} relative increase")
    md.append(f"- **Hallucination**: {hr_B:.3f} (B) -> {hr_A:.3f} (A), {hall_desc} "
              f"(p={t['p']:.2e}). H3's >=30% hallucination reduction is "
              f"{'SUPPORTED' if hall_change >= 0.30 else 'NOT met'}.")
    md.append("\nSee discussion of converged conformance and the "
              "coverage/precision trade-off in the README.\n")
    (RES / "summary.md").write_text("\n".join(md))


def _safe_drop(b, a):
    return (b - a) / b if b else 0.0


def _figures(rows, k):
    fig, ax = plt.subplots(2, 2, figsize=(11, 8))
    # Conformance bars
    fp = [st.mean(_rate(rows, "A", "first_pass")), st.mean(_rate(rows, "B", "first_pass"))]
    cv = [st.mean(_rate(rows, "A", "converged")), st.mean(_rate(rows, "B", "converged"))]
    x = range(2)
    ax[0][0].bar([i - 0.2 for i in x], fp, 0.4, label="first-pass")
    ax[0][0].bar([i + 0.2 for i in x], cv, 0.4, label="converged")
    ax[0][0].set_xticks(list(x)); ax[0][0].set_xticklabels(["System A", "System B"])
    ax[0][0].set_ylabel("conformance"); ax[0][0].set_title("Deney 1: SHACL conformance")
    ax[0][0].legend()
    # Convergence curve
    ax[0][1].plot(range(k), _conv_curve(rows, "A", k), "o-", label="System A")
    ax[0][1].plot(range(k), _conv_curve(rows, "B", k), "s-", label="System B")
    ax[0][1].set_xlabel("iteration"); ax[0][1].set_ylabel("cum. conformance")
    ax[0][1].set_title("Convergence (k=%d)" % k); ax[0][1].legend()
    ax[0][1].set_xticks(range(k))
    # Hallucination box
    ax[1][0].boxplot([_vals(rows, "A", "hr"), _vals(rows, "B", "hr")],
                     tick_labels=["System A", "System B"])
    ax[1][0].set_ylabel("hallucination rate")
    ax[1][0].set_title("Deney 2: hallucination rate")
    # Token efficiency
    ax[1][1].bar(["System A", "System B"],
                 [st.mean(_vals(rows, "A", "tok_eff")), st.mean(_vals(rows, "B", "tok_eff"))])
    ax[1][1].set_ylabel("grounded / token")
    ax[1][1].set_title("Deney 3: token efficiency")
    fig.tight_layout()
    fig.savefig(RES / "figures" / "rq3_results.png", dpi=120)
    plt.close(fig)


def _print_headline(rows, S, provider):
    n = len(rows)
    print(f"\n=== RQ3 results ({n} questions, provider={provider.name}) ===")
    print(f"First-pass conformance:  A={st.mean(_rate(rows,'A','first_pass')):.0%}  "
          f"B={st.mean(_rate(rows,'B','first_pass')):.0%}  "
          f"(McNemar p={S['fp_mcnemar']['p']:.2e})")
    print(f"Converged conformance:   A={st.mean(_rate(rows,'A','converged')):.0%}  "
          f"B={st.mean(_rate(rows,'B','converged')):.0%}  "
          f"(McNemar p={S['cv_mcnemar']['p']:.2e})")
    print(f"Hallucination rate:      A={st.mean(_vals(rows,'A','hr')):.3f}  "
          f"B={st.mean(_vals(rows,'B','hr')):.3f}  "
          f"({S['hr_test']['test']} p={S['hr_test']['p']:.2e}, d={S['hr_cohens_d']:.2f})")
    print(f"Coverage:                A={st.mean(_vals(rows,'A','coverage')):.2f}  "
          f"B={st.mean(_vals(rows,'B','coverage')):.2f}")
    print(f"Token efficiency:        A={st.mean(_vals(rows,'A','tok_eff')):.4f}  "
          f"B={st.mean(_vals(rows,'B','tok_eff')):.4f}  "
          f"(p={S['eff_test']['p']:.2e})")
    print(f"Results -> {RES}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Run the RQ3 controlled experiment.")
    ap.add_argument("--n", type=int, default=None, help="limit #questions (debug)")
    ap.add_argument("--k", type=int, default=K)
    args = ap.parse_args()
    run(n=args.n, k=args.k)


if __name__ == "__main__":
    main()
