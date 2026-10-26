"""
make_figures.py — render report figures from the experiment CSVs (§2 deliverable).

Produces (into results/figures/):
  fig1_recall_by_type.png   — Set A vs Set B recall per inconsistency type
  fig2_governance.png       — cross-holon detection rate + latency vs N

Reads results/metrics.csv (run_experiment.py) and results/governance.csv
(governance_validation.py). Run those first.
"""
from __future__ import annotations

import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

_PROJ = Path(__file__).resolve().parents[1]
RESULTS = _PROJ / "results"
FIGDIR = RESULTS / "figures"


def fig_recall_by_type() -> None:
    rows = list(csv.DictReader((RESULTS / "metrics.csv").open()))
    types = ["T1", "T2", "T3", "T4", "T5", "T6"]
    a = [next(float(r["recall"]) for r in rows if r["type"] == t and r["set"] == "A") for t in types]
    b = [next(float(r["recall"]) for r in rows if r["type"] == t and r["set"] == "B") for t in types]

    x = range(len(types))
    w = 0.38
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar([i - w / 2 for i in x], a, w, label="Set A (boundary-aware)", color="#2a6f97")
    ax.bar([i + w / 2 for i in x], b, w, label="Set B (flat)", color="#e09f3e")
    ax.set_xticks(list(x)); ax.set_xticklabels(types)
    ax.set_ylabel("Recall (detection rate)"); ax.set_ylim(0, 1.08)
    ax.set_title("Inconsistency detection by type — boundary-aware vs flat SHACL")
    ax.axvspan(2.5, 5.5, color="#cce3de", alpha=0.35, zorder=0)
    ax.text(4, 1.02, "boundary-only (T4–T6)", ha="center", fontsize=9, color="#1b4332")
    ax.legend(loc="lower left"); fig.tight_layout()
    fig.savefig(FIGDIR / "fig1_recall_by_type.png", dpi=150)
    plt.close(fig)


def fig_governance() -> None:
    rows = list(csv.DictReader((RESULTS / "governance.csv").open()))
    regimes = ["C1", "C2", "C3"]
    label = {"C1": "Centralized", "C2": "Federated", "C3": "Autonomous"}
    color = {"C1": "#9d0208", "C2": "#2a6f97", "C3": "#6c757d"}
    sizes = sorted({int(r["n_holons"]) for r in rows})

    def _num(s):
        try:
            return float(s)
        except (ValueError, TypeError):
            return None     # "n/a" / "impractical(...)" -> skip (e.g. capped C1)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4))
    for rg in regimes:
        xs_d, ys_d, xs_l, ys_l = [], [], [], []
        for n in sizes:
            row = next(r for r in rows if r["regime"] == rg and int(r["n_holons"]) == n)
            d, l = _num(row["detection_rate"]), _num(row["latency_s"])
            if d is not None:
                xs_d.append(n); ys_d.append(d)
            if l is not None:
                xs_l.append(n); ys_l.append(l)
        ax1.plot(xs_d, ys_d, "o-", label=label[rg], color=color[rg])
        ax2.plot(xs_l, ys_l, "o-", label=label[rg], color=color[rg])

    ax1.set_title("Cross-holon detection rate"); ax1.set_xlabel("N holons")
    ax1.set_ylabel("detection rate"); ax1.set_ylim(-0.05, 1.1); ax1.legend()
    ax2.set_title("Validation latency"); ax2.set_xlabel("N holons")
    ax2.set_ylabel("seconds"); ax2.legend()
    fig.suptitle("Governance topology: detection vs cost trade-off (§2.7)")
    fig.tight_layout()
    fig.savefig(FIGDIR / "fig2_governance.png", dpi=150)
    plt.close(fig)


def main() -> None:
    FIGDIR.mkdir(parents=True, exist_ok=True)
    fig_recall_by_type()
    fig_governance()
    print(f"Figures written to {FIGDIR}")


if __name__ == "__main__":
    main()
