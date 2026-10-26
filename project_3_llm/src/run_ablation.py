"""run_ablation.py — 2x2 factorial ablation for RQ3 (reviewer request).

System A and System B differ in TWO design factors at once, so the A-vs-B
contrast cannot attribute the effect. This runner adds the two middle-ground
systems and runs all four over the same question set, provider and metrics:

    | System | Retrieval (context)      | Prompt              |
    |--------|--------------------------|---------------------|
    | A      | boundary-scoped holon    | SHACL-guided        |
    | C      | boundary-scoped holon    | naive (no shape)    |
    | D      | naive top-k union        | SHACL-guided        |
    | B      | naive top-k union        | naive (no shape)    |

Planned contrasts (each isolates one factor, plus the original combined one):

    A vs C : SHACL-prompt effect under boundary retrieval
    D vs B : SHACL-prompt effect under naive retrieval
    A vs D : boundary-retrieval effect under SHACL prompting
    C vs B : boundary-retrieval effect under naive prompting
    A vs B : combined effect (the original RQ3 comparison)

Metrics per system: first-pass/converged SHACL conformance (McNemar per
contrast), hallucination rate (paired Shapiro -> t/Wilcoxon, Cohen's d),
coverage, context tokens and token efficiency — the §3.3 suite.

Writes results/ablation/{conformance,hallucination,efficiency}.csv,
results/ablation/summary.md and results/ablation/figures/ablation.png.
Deterministic on the default mock provider; a real LLM activates via
P3_LLM_PROVIDER (same contract as run_experiment).

Run:
    python src/run_ablation.py [--n N] [--k K]
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

_SRC = Path(__file__).resolve().parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
# Project 2 must come AFTER this project: both projects have a run_experiment.py
# and we need project_3's (project 2 only supplies shacl_validator here).
_P2_SRC = _SRC.parents[1] / "project_2_semantic" / "src"
if str(_P2_SRC) not in sys.path:
    sys.path.append(str(_P2_SRC))

from dataset import grounding_graph_for                            # noqa: E402
from graph_rag import DualRAG                                       # noqa: E402
from evaluation import evaluate_generation                          # noqa: E402
from llm_generator import generate                                  # noqa: E402
from llm_provider import get_provider                               # noqa: E402
from run_experiment import (K, P2_SHAPES_A, _cumulative,            # noqa: E402
                            cohens_d_paired, mcnemar_binary, paired_test)
from shacl_to_prompt import load_shapes as load_shape_templates, node_shapes, transform  # noqa: E402
from shacl_validator import load_ontology, load_shapes             # noqa: E402

_PROJ = _SRC.parent
RES = _PROJ / "results" / "ablation"

SYSTEMS = ("A", "C", "D", "B")               # factorial order for tables
FACTORS = {                                   # (retrieval, prompt)
    "A": ("boundary", "SHACL"),
    "C": ("boundary", "naive"),
    "D": ("naive", "SHACL"),
    "B": ("naive", "naive"),
}
CONTRASTS = [
    ("A", "C", "SHACL prompt | boundary retrieval"),
    ("D", "B", "SHACL prompt | naive retrieval"),
    ("A", "D", "boundary retrieval | SHACL prompt"),
    ("C", "B", "boundary retrieval | naive prompt"),
    ("A", "B", "combined (original RQ3 contrast)"),
]


# --------------------------------------------------------------------------- #
# Experiment driver
# --------------------------------------------------------------------------- #

def run(n=None, k=K, provider=None, questions=None, systems=SYSTEMS):
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
        grounding = grounding_graph_for(q)
        for sysname in systems:
            ctx = rag.context(q, sysname)
            gres = generate(template, ctx.to_generator_context(), system=sysname,
                            provider=provider, grounding=grounding,
                            shapes_graph=shapes, ont_graph=ont, k=k,
                            write=False)
            hrep = evaluate_generation(gres.output_ttl, q, sysname)
            rec[sysname] = {
                "first_pass": gres.first_pass, "converged": gres.passed,
                "iters": gres.iterations,
                "cum_conform": _cumulative(gres.per_iter_conforms, k),
                "hr": hrep.hallucination_rate, "coverage": hrep.coverage,
                "p_at_3": hrep.precision_at_3, "grounded": hrep.grounded,
                "a": hrep.type_a, "b": hrep.type_b, "c": hrep.type_c,
                "ctx_tokens": ctx.context_tokens,
                "gen_tokens": gres.total_tokens,
                "tok_eff": hrep.grounded / gres.total_tokens if gres.total_tokens else 0.0,
            }
        rows.append(rec)
    elapsed = time.perf_counter() - t0
    _write_all(rows, k, elapsed, provider, systems)
    return rows


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #

def _vals(rows, s, key):
    return [r[s][key] for r in rows]


def _rate(rows, s, key):
    return [1.0 if r[s][key] else 0.0 for r in rows]


def _bools(rows, s, key):
    return [bool(r[s][key]) for r in rows]


def _write_all(rows, k, elapsed, provider, systems):
    (RES / "figures").mkdir(parents=True, exist_ok=True)

    with (RES / "conformance.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["holon_id"]
                   + [f"fp_{s}" for s in systems]
                   + [f"conv_{s}" for s in systems]
                   + [f"iters_{s}" for s in systems])
        for r in rows:
            w.writerow([r["holon_id"]]
                       + [r[s]["first_pass"] for s in systems]
                       + [r[s]["converged"] for s in systems]
                       + [r[s]["iters"] for s in systems])

    with (RES / "hallucination.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["holon_id"]
                   + [f"hr_{s}" for s in systems]
                   + [f"cov_{s}" for s in systems]
                   + [f"{s}_typeA" for s in systems]
                   + [f"{s}_typeB" for s in systems]
                   + [f"{s}_typeC" for s in systems])
        for r in rows:
            w.writerow([r["holon_id"]]
                       + [f"{r[s]['hr']:.3f}" for s in systems]
                       + [f"{r[s]['coverage']:.2f}" for s in systems]
                       + [r[s]["a"] for s in systems]
                       + [r[s]["b"] for s in systems]
                       + [r[s]["c"] for s in systems])

    with (RES / "efficiency.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["holon_id"]
                   + [f"ctxTok_{s}" for s in systems]
                   + [f"genTok_{s}" for s in systems]
                   + [f"tokEff_{s}" for s in systems])
        for r in rows:
            w.writerow([r["holon_id"]]
                       + [r[s]["ctx_tokens"] for s in systems]
                       + [r[s]["gen_tokens"] for s in systems]
                       + [f"{r[s]['tok_eff']:.5f}" for s in systems])

    contrasts = _contrast_stats(rows)
    _write_summary(rows, k, elapsed, provider, systems, contrasts)
    _figures(rows, systems)
    _print_headline(rows, systems, contrasts, provider)


def _contrast_stats(rows):
    out = []
    for x, y, label in CONTRASTS:
        fp = mcnemar_binary(_bools(rows, x, "first_pass"), _bools(rows, y, "first_pass"))
        cv = mcnemar_binary(_bools(rows, x, "converged"), _bools(rows, y, "converged"))
        hr = paired_test(_vals(rows, y, "hr"), _vals(rows, x, "hr"))   # y - x
        d = cohens_d_paired(_vals(rows, y, "hr"), _vals(rows, x, "hr"))
        out.append({"x": x, "y": y, "label": label,
                    "fp_mcnemar": fp, "cv_mcnemar": cv, "hr_test": hr, "hr_d": d})
    return out


def _write_summary(rows, k, elapsed, provider, systems, contrasts):
    n = len(rows)
    md = []
    md.append("# RQ3 Ablation — 2x2 Factorial (retrieval x prompt)\n")
    md.append(f"- Questions: **{n}**  ·  k = {k}  ·  LLM provider: "
              f"**{provider.name}** ({provider.model})  ·  wall-clock {elapsed:.1f}s\n")
    md.append("\n| System | Retrieval | Prompt |")
    md.append("|--------|-----------|--------|")
    for s in systems:
        r, p = FACTORS[s]
        md.append(f"| {s} | {r} | {p} |")

    md.append("\n## Per-system metrics\n")
    md.append("| Metric | " + " | ".join(f"System {s}" for s in systems) + " |")
    md.append("|--------|" + "----------|" * len(systems))
    metric_rows = [
        ("First-pass conformance", lambda s: f"{st.mean(_rate(rows, s, 'first_pass')):.0%}"),
        (f"Converged conformance (k={k})", lambda s: f"{st.mean(_rate(rows, s, 'converged')):.0%}"),
        ("Mean hallucination rate", lambda s: f"{st.mean(_vals(rows, s, 'hr')):.3f}"),
        ("Information coverage", lambda s: f"{st.mean(_vals(rows, s, 'coverage')):.2f}"),
        ("Mean context tokens", lambda s: f"{st.mean(_vals(rows, s, 'ctx_tokens')):.0f}"),
        ("Token efficiency (grounded/token)", lambda s: f"{st.mean(_vals(rows, s, 'tok_eff')):.4f}"),
        ("Type A / B / C totals", lambda s: (f"{sum(r[s]['a'] for r in rows)} / "
                                             f"{sum(r[s]['b'] for r in rows)} / "
                                             f"{sum(r[s]['c'] for r in rows)}")),
    ]
    for name, fn in metric_rows:
        md.append(f"| {name} | " + " | ".join(fn(s) for s in systems) + " |")

    md.append("\n## Contrasts (one factor isolated per row)\n")
    md.append("| Contrast | Factor isolated | FP McNemar p | Conv McNemar p | "
              "Halluc. test | Halluc. p | Cohen's d |")
    md.append("|----------|-----------------|--------------|----------------|"
              "--------------|-----------|-----------|")
    for c in contrasts:
        t = c["hr_test"]
        md.append(f"| {c['x']} vs {c['y']} | {c['label']} "
                  f"| {c['fp_mcnemar']['p']:.3e} | {c['cv_mcnemar']['p']:.3e} "
                  f"| {t['test']} | {t['p']:.3e} | {c['hr_d']:.2f} |")

    md.append("\n## Factorial reading\n")
    fp = {s: st.mean(_rate(rows, s, "first_pass")) for s in systems}
    hr = {s: st.mean(_vals(rows, s, "hr")) for s in systems}
    md.append(f"- **Prompt (SHACL) main effect on first-pass conformance**: "
              f"boundary arm {fp['A'] - fp['C']:+.0%} (A-C), "
              f"naive arm {fp['D'] - fp['B']:+.0%} (D-B).")
    md.append(f"- **Retrieval (boundary) main effect on hallucination**: "
              f"SHACL arm {hr['D'] - hr['A']:+.3f} (D-A), "
              f"naive arm {hr['B'] - hr['C']:+.3f} (B-C).")
    md.append("- If the SHACL-prompt effect is concentrated in conformance and "
              "the boundary-retrieval effect in hallucination, the two design "
              "changes are separable and each is individually attributable.\n")
    (RES / "summary.md").write_text("\n".join(md))


def _figures(rows, systems):
    fig, ax = plt.subplots(1, 3, figsize=(14, 4.2))
    labels = [f"{s}\n({FACTORS[s][0]}/{FACTORS[s][1]})" for s in systems]
    x = range(len(systems))
    fp = [st.mean(_rate(rows, s, "first_pass")) for s in systems]
    cv = [st.mean(_rate(rows, s, "converged")) for s in systems]
    ax[0].bar([i - 0.2 for i in x], fp, 0.4, label="first-pass")
    ax[0].bar([i + 0.2 for i in x], cv, 0.4, label="converged")
    ax[0].set_xticks(list(x)); ax[0].set_xticklabels(labels, fontsize=8)
    ax[0].set_ylabel("conformance"); ax[0].set_title("SHACL conformance")
    ax[0].legend()
    ax[1].boxplot([_vals(rows, s, "hr") for s in systems], tick_labels=labels)
    ax[1].tick_params(axis="x", labelsize=8)
    ax[1].set_ylabel("hallucination rate"); ax[1].set_title("Hallucination")
    ax[2].bar(list(x), [st.mean(_vals(rows, s, "ctx_tokens")) for s in systems])
    ax[2].set_xticks(list(x)); ax[2].set_xticklabels(labels, fontsize=8)
    ax[2].set_ylabel("mean context tokens"); ax[2].set_title("Context size")
    fig.tight_layout()
    fig.savefig(RES / "figures" / "ablation.png", dpi=120)
    plt.close(fig)


def _print_headline(rows, systems, contrasts, provider):
    n = len(rows)
    print(f"\n=== RQ3 ablation ({n} questions, provider={provider.name}) ===")
    print(f"{'system':>8} {'retrieval':>10} {'prompt':>7} {'first-pass':>11} "
          f"{'converged':>10} {'halluc':>7} {'ctx_tok':>8}")
    for s in systems:
        r, p = FACTORS[s]
        print(f"{s:>8} {r:>10} {p:>7} "
              f"{st.mean(_rate(rows, s, 'first_pass')):>11.0%} "
              f"{st.mean(_rate(rows, s, 'converged')):>10.0%} "
              f"{st.mean(_vals(rows, s, 'hr')):>7.3f} "
              f"{st.mean(_vals(rows, s, 'ctx_tokens')):>8.0f}")
    print("\ncontrasts:")
    for c in contrasts:
        print(f"  {c['x']} vs {c['y']:<2} ({c['label']}): "
              f"fp p={c['fp_mcnemar']['p']:.2e}  "
              f"halluc p={c['hr_test']['p']:.2e} d={c['hr_d']:.2f}")
    print(f"Results -> {RES}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Run the RQ3 2x2 ablation (A/B/C/D).")
    ap.add_argument("--n", type=int, default=None, help="limit #questions (debug)")
    ap.add_argument("--k", type=int, default=K)
    args = ap.parse_args()
    run(n=args.n, k=args.k)


if __name__ == "__main__":
    main()
