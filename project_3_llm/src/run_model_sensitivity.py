"""Reproducible real-model sensitivity analysis for the article.

Selects the first question (in dataset order) from each specialty and evaluates
the same paired System-A/System-B prompts with each local Ollama model. Full
per-question outputs remain under results/model_sensitivity/<model>/.
"""
from __future__ import annotations

import argparse
import csv
import statistics as st
from pathlib import Path

import run_experiment as experiment
from graph_rag import DualRAG
from llm_provider import get_provider

DEFAULT_MODELS = ("qwen3:8b", "llama3.1:8b", "gemma3:4b")
OUT = Path(__file__).resolve().parents[1] / "results" / "model_sensitivity"


def stratified_questions(per_specialty: int = 1):
    selected, counts = [], {}
    for question in DualRAG().questions:
        count = counts.get(question.specialty, 0)
        if count < per_specialty:
            selected.append(question)
            counts[question.specialty] = count + 1
    return selected


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
    original_res = experiment.RES
    try:
        for model in args.models:
            slug = model.replace(":", "-").replace("/", "-")
            experiment.RES = OUT / slug
            rows = experiment.run(
                k=args.k,
                provider=get_provider("ollama", model),
                questions=questions,
                write_generated=False,
            )
            summaries.append({
                "model": model,
                "n": len(rows),
                "fp_A": mean(rows, "A", "first_pass"),
                "fp_B": mean(rows, "B", "first_pass"),
                "conv_A": mean(rows, "A", "converged"),
                "conv_B": mean(rows, "B", "converged"),
                "hall_A": mean(rows, "A", "hr"),
                "hall_B": mean(rows, "B", "hr"),
                "cov_A": mean(rows, "A", "coverage"),
                "cov_B": mean(rows, "B", "coverage"),
                "tokens_A": mean(rows, "A", "gen_tokens"),
                "tokens_B": mean(rows, "B", "gen_tokens"),
            })
    finally:
        experiment.RES = original_res

    fields = list(summaries[0])
    with (OUT / "comparison.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(summaries)

    lines = [
        "# Real-model sensitivity analysis",
        "",
        f"Specialty-stratified sample: {len(questions)} questions; repair budget: k={args.k}.",
        "",
        "| Model | First pass A/B | Converged A/B | Hallucination A/B | Coverage A/B |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in summaries:
        lines.append(
            f"| {row['model']} | {row['fp_A']:.0%}/{row['fp_B']:.0%} | "
            f"{row['conv_A']:.0%}/{row['conv_B']:.0%} | "
            f"{row['hall_A']:.3f}/{row['hall_B']:.3f} | "
            f"{row['cov_A']:.2f}/{row['cov_B']:.2f} |")
    (OUT / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
