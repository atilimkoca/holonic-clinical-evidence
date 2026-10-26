"""Real-model 2x2 ablation (A/C/D/B) on the sensitivity sample.

Mirrors run_model_sensitivity.py but evaluates all four ablation systems
(run_ablation.SYSTEMS) with each local Ollama model on the same
specialty-stratified question sample, so the factor attribution measured
deterministically in run_ablation.py is also checked against real providers.
System A/B completions replay from the response cache when the primary
sensitivity analysis has already run.

Writes results/ablation_sensitivity/<model>/ (per-model ablation outputs)
plus results/ablation_sensitivity/{comparison.csv,summary.md}.

Run:
    python src/run_ablation_sensitivity.py            # all three models
    python src/run_ablation_sensitivity.py --models qwen3:8b
"""
from __future__ import annotations

import argparse
import csv
import statistics as st
from pathlib import Path

import run_ablation as ablation
from llm_provider import get_provider
from run_ablation import FACTORS, SYSTEMS
from run_model_sensitivity import DEFAULT_MODELS, stratified_questions

OUT = Path(__file__).resolve().parents[1] / "results" / "ablation_sensitivity"


def mean(rows, system, metric):
    return st.mean(float(row[system][metric]) for row in rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", nargs="+", default=list(DEFAULT_MODELS))
    parser.add_argument("--per-specialty", type=int, default=1)
    parser.add_argument("--k", type=int, default=3)
    args = parser.parse_args()

    questions = stratified_questions(args.per_specialty)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "sample.txt").write_text(
        "\n".join(f"{q.specialty}\t{q.holon_id}" for q in questions) + "\n")

    summaries = []
    original_res = ablation.RES
    try:
        for model in args.models:
            slug = model.replace(":", "-").replace("/", "-")
            ablation.RES = OUT / slug
            rows = ablation.run(
                k=args.k,
                provider=get_provider("ollama", model),
                questions=questions,
            )
            summary = {"model": model, "n": len(rows)}
            for s in SYSTEMS:
                summary[f"fp_{s}"] = mean(rows, s, "first_pass")
                summary[f"conv_{s}"] = mean(rows, s, "converged")
                summary[f"hall_{s}"] = mean(rows, s, "hr")
                summary[f"cov_{s}"] = mean(rows, s, "coverage")
            summaries.append(summary)
    finally:
        ablation.RES = original_res

    fields = list(summaries[0])
    with (OUT / "comparison.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(summaries)

    order = " / ".join(f"{s}={FACTORS[s][0]}+{FACTORS[s][1]}" for s in SYSTEMS)
    lines = [
        "# Real-model 2x2 ablation (retrieval x prompt)",
        "",
        f"Specialty-stratified sample: {len(questions)} questions; "
        f"repair budget: k={args.k}.",
        f"Systems: {order}.",
        "",
        "| Model | First pass A/C/D/B | Converged A/C/D/B | "
        "Hallucination A/C/D/B |",
        "|---|---:|---:|---:|",
    ]
    for row in summaries:
        fp = "/".join(f"{row[f'fp_{s}']:.0%}" for s in SYSTEMS)
        cv = "/".join(f"{row[f'conv_{s}']:.0%}" for s in SYSTEMS)
        hl = "/".join(f"{row[f'hall_{s}']:.2f}" for s in SYSTEMS)
        lines.append(f"| {row['model']} | {fp} | {cv} | {hl} |")
    (OUT / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
