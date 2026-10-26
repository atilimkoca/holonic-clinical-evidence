"""run_three_sets.py — RQ2 extended: Set A vs Set B vs Set C (reviewer request).

Adds the third condition to the RQ2 detection comparison:

    Set A : boundary-aware SHACL           on the holonic corpus
    Set B : flat SHACL                     on the holonic corpus
    Set C : context-aware SPARQL SHACL     on the FLAT-RDF export of the corpus
            (schema-level threshold constant; membership/aggregate leftovers)

Set C isolates WHERE Set A's advantage comes from: if C matches A, the
detection gain is attributable to SPARQL expressiveness (recoverable on flat
data, with the documented representational costs); wherever C trails A, the
boundary REPRESENTATION itself is required.

Pipeline (per set): validate every corpus holon (severity >= Violation),
score against the gold manifest, per-type + overall P/R/F1, pairwise McNemar
(A-B, A-C, C-B) and bootstrap CIs on recall.

Writes results/three_sets/{outcomes,metrics,contingency}.csv and summary.md.

Run (regenerate the flat export first if the corpus changed):
    python src/flatten_corpus.py
    python src/run_three_sets.py
"""
from __future__ import annotations

import argparse
import csv
import time
from collections import defaultdict
from pathlib import Path

from statsmodels.stats.contingency_tables import mcnemar

from shacl_validator import detect, load_ontology, load_shapes

_PROJ = Path(__file__).resolve().parents[1]
SET_A = _PROJ / "shacl" / "shapes" / "boundary_aware"
SET_B = _PROJ / "shacl" / "shapes" / "flat"
SET_C = _PROJ / "shacl" / "shapes" / "flat_context_aware"

SETS = ("A", "B", "C")
PAIRS = (("A", "B"), ("A", "C"), ("C", "B"))
GOLD_TYPES = ("T1", "T2", "T3", "T4", "T5", "T6")


def _prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)
          if (precision + recall) else 0.0)
    return precision, recall, f1


def run(corpus_dir: Path, flat_dir: Path, results_dir: Path) -> None:
    results_dir.mkdir(parents=True, exist_ok=True)
    manifest = list(csv.DictReader((corpus_dir / "manifest.csv").open()))

    ont = load_ontology()
    shapes = {"A": load_shapes(SET_A), "B": load_shapes(SET_B),
              "C": load_shapes(SET_C)}
    # Set C validates the flat export; A and B the holonic serialisation.
    data_dir = {"A": corpus_dir, "B": corpus_dir, "C": flat_dir}

    rows, lat = [], {s: 0.0 for s in SETS}
    for r in manifest:
        gold_inconsistent = (r["gold_label"] != "C")
        row = {"holon_id": r["holon_id"], "gold_label": r["gold_label"],
               "gold_inconsistent": gold_inconsistent}
        for s in SETS:
            f = data_dir[s] / r["file"]
            t0 = time.perf_counter()
            flagged, _ = detect(f, shapes[s], ont)
            lat[s] += time.perf_counter() - t0
            row[f"flagged_{s}"] = flagged
            row[f"correct_{s}"] = flagged == gold_inconsistent
        rows.append(row)

    _write_outcomes(results_dir, rows)
    metrics = _metrics(rows)
    _write_metrics(results_dir, metrics)
    tests = {pair: _mcnemar(rows, *pair) for pair in PAIRS}
    ci = _bootstrap_cis(rows)
    _write_summary(results_dir, rows, metrics, tests, lat, ci)
    _write_contingency(results_dir, tests)

    print(f"Holons evaluated: {len(rows)}")
    for s in SETS:
        print(f"Set {s}: overall F1={metrics['ALL'][s][2]:.3f} "
              f"recall={metrics['ALL'][s][1]:.3f} latency={lat[s]:.1f}s")
    for (x, y), (table, res) in tests.items():
        print(f"McNemar {x} vs {y}: discordant {table[0][1]}/{table[1][0]}, "
              f"p={res.pvalue:.3e}")
    print(f"Results written to {results_dir}")


def _write_outcomes(results_dir: Path, rows: list[dict]) -> None:
    with (results_dir / "outcomes.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def _metrics(rows: list[dict]) -> dict:
    consistent = [r for r in rows if not r["gold_inconsistent"]]
    by_type: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if r["gold_inconsistent"]:
            by_type[r["gold_label"]].append(r)

    out: dict[str, dict] = {}
    for t in sorted(by_type) + ["ALL"]:
        items = rows if t == "ALL" else by_type[t] + consistent
        per = {}
        for s in SETS:
            flag = f"flagged_{s}"
            tp = sum(1 for r in items if r["gold_inconsistent"] and r[flag])
            fp = sum(1 for r in items if not r["gold_inconsistent"] and r[flag])
            fn = sum(1 for r in items if r["gold_inconsistent"] and not r[flag])
            tn = sum(1 for r in items if not r["gold_inconsistent"] and not r[flag])
            per[s] = (*_prf(tp, fp, fn), tp, fp, fn, tn)
        out[t] = per
    return out


def _write_metrics(results_dir: Path, metrics: dict) -> None:
    with (results_dir / "metrics.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["type", "set", "precision", "recall", "f1",
                    "TP", "FP", "FN", "TN"])
        for t, per in metrics.items():
            for s, vals in per.items():
                p, rc, f1, tp, fp, fn, tn = vals
                w.writerow([t, s, f"{p:.3f}", f"{rc:.3f}", f"{f1:.3f}",
                            tp, fp, fn, tn])


def _mcnemar(rows: list[dict], x: str, y: str):
    n00 = sum(1 for r in rows if r[f"correct_{x}"] and r[f"correct_{y}"])
    n01 = sum(1 for r in rows if r[f"correct_{x}"] and not r[f"correct_{y}"])
    n10 = sum(1 for r in rows if not r[f"correct_{x}"] and r[f"correct_{y}"])
    n11 = sum(1 for r in rows if not r[f"correct_{x}"] and not r[f"correct_{y}"])
    table = [[n00, n01], [n10, n11]]
    return table, mcnemar(table, exact=True)


def _bootstrap_cis(rows: list[dict], n_boot: int = 2000, seed: int = 42) -> dict:
    """95% bootstrap CIs for each set's recall over the inconsistent holons and
    for the pairwise recall differences."""
    import random
    rng = random.Random(seed)
    incon = [r for r in rows if r["gold_inconsistent"]]
    n = len(incon)

    def recall(sample, s):
        return sum(1 for r in sample if r[f"flagged_{s}"]) / len(sample)

    boots = {s: [] for s in SETS}
    diffs = {pair: [] for pair in PAIRS}
    for _ in range(n_boot):
        sample = [incon[rng.randrange(n)] for _ in range(n)]
        rec = {s: recall(sample, s) for s in SETS}
        for s in SETS:
            boots[s].append(rec[s])
        for (x, y) in PAIRS:
            diffs[(x, y)].append(rec[x] - rec[y])

    def ci(b):
        b = sorted(b)
        return b[int(0.025 * len(b))], b[int(0.975 * len(b))]

    out = {s: (recall(incon, s), *ci(boots[s])) for s in SETS}
    for (x, y) in PAIRS:
        out[f"{x}-{y}"] = (recall(incon, x) - recall(incon, y), *ci(diffs[(x, y)]))
    return out


def _write_summary(results_dir: Path, rows, metrics, tests, lat, ci) -> None:
    n = len(rows)
    md = []
    md.append("# RQ2 Extended — Boundary-Aware (A) vs Flat (B) vs "
              "Flat + Context-Aware SPARQL (C)\n")
    md.append(f"- Corpus size: **{n}** holons "
              f"({sum(1 for r in rows if r['gold_inconsistent'])} inconsistent, "
              f"{sum(1 for r in rows if not r['gold_inconsistent'])} consistent)")
    md.append("- Set A and Set B validate the holonic serialisation; Set C "
              "validates the flat-RDF export (src/flatten_corpus.py).")
    md.append("- Validation latency (total): "
              + ", ".join(f"Set {s} {lat[s]:.1f}s" for s in SETS) + "\n")

    md.append("\n## Per-type Recall / F1\n")
    md.append("| Type | A recall | B recall | C recall | A F1 | B F1 | C F1 |")
    md.append("|------|----------|----------|----------|------|------|------|")
    for t in list(GOLD_TYPES) + ["ALL"]:
        if t not in metrics:
            continue
        a, b, c = metrics[t]["A"], metrics[t]["B"], metrics[t]["C"]
        md.append(f"| {t} | {a[1]:.2f} | {b[1]:.2f} | {c[1]:.2f} "
                  f"| {a[2]:.2f} | {b[2]:.2f} | {c[2]:.2f} |")

    md.append("\n## Pairwise McNemar (paired correctness)\n")
    md.append("| Pair | Discordant (x-right/y-wrong) | Discordant (x-wrong/y-right) "
              "| statistic | p |")
    md.append("|------|------------------------------|------------------------------"
              "|-----------|---|")
    for (x, y), (table, res) in tests.items():
        md.append(f"| {x} vs {y} | {table[0][1]} | {table[1][0]} "
                  f"| {res.statistic} | {res.pvalue:.3e} |")

    md.append("\n## 95% Bootstrap CIs (recall on inconsistent holons)\n")
    md.append("| Quantity | Point estimate | 95% CI |")
    md.append("|----------|----------------|--------|")
    for key in list(SETS) + [f"{x}-{y}" for (x, y) in PAIRS]:
        v = ci[key]
        label = f"Set {key} recall" if key in SETS else f"Recall difference ({key})"
        md.append(f"| {label} | {v[0]:.2f} | [{v[1]:.2f}, {v[2]:.2f}] |")

    md.append("\n## Interpretation\n")
    md.append("Set C measures how much of Set A's detection advantage a "
              "context-aware SPARQL author can recover WITHOUT the boundary "
              "representation. Its T4a check hard-codes the schema-level 0.50 "
              "threshold (the per-holon admission rule is not representable in "
              "flat RDF), and its T5/T6 checks survive only because the flat "
              "export retains holon-membership and aggregate-summary facts. "
              "Detection parity with Set A therefore does NOT make the two "
              "designs equivalent: the recovered checks are corpus-specific "
              "constants and leftover facts rather than a reusable boundary "
              "contract, and the same boundary additionally serves retrieval, "
              "LLM grounding, projection and governance (RQ3/RQ4).\n")

    (results_dir / "summary.md").write_text("\n".join(md))


def _write_contingency(results_dir: Path, tests) -> None:
    with (results_dir / "contingency.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["pair", "n00", "n01", "n10", "n11", "statistic", "p_value"])
        for (x, y), (table, res) in tests.items():
            w.writerow([f"{x}-{y}", table[0][0], table[0][1],
                        table[1][0], table[1][1], res.statistic, res.pvalue])


def main() -> None:
    ap = argparse.ArgumentParser(description="Run the extended RQ2 (A/B/C) experiment.")
    ap.add_argument("--corpus", default=str(_PROJ / "corpus" / "holons"))
    ap.add_argument("--flat", default=str(_PROJ / "corpus" / "holons_flat"))
    ap.add_argument("--results", default=str(_PROJ / "results" / "three_sets"))
    args = ap.parse_args()
    run(Path(args.corpus), Path(args.flat), Path(args.results))


if __name__ == "__main__":
    main()
