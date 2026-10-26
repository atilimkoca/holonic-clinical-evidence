"""context_budget.py — Context Budget Problem: knapsack selection + scalability (§3.4).

Given a token limit L and a set of holons, each with a token cost t(h) and an
information value v(h), choose the subset maximising value within budget:

    maximize   sum_i v(h_i) * x_i
    subject to sum_i t(h_i) * x_i <= L,   x_i in {0,1}

This is 0/1 knapsack (NP-hard; proof in theory/context_budget_nphard.md). We
ship:
  * `greedy_knapsack` — the modified ratio-greedy (provably 1/2-approximate);
  * `dp_knapsack`     — exact DP, to *measure* the empirical approximation ratio;
  * `latency_compare` — naive O(|V|) full-triple scan vs holon-based O(d*b);
  * `scalability_sweep` — 100/500/1000/5000 holons (subsample + synthetic
    replication, seed 42) -> results/performance/scalability.csv + figure.
"""
from __future__ import annotations

import csv
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

_SRC = Path(__file__).resolve().parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from dataset import load_corpus, load_testset            # noqa: E402
from graph_rag import DualRAG                              # noqa: E402
from llm_provider import estimate_tokens                   # noqa: E402

_PROJ = _SRC.parent
PERF_DIR = _PROJ / "results" / "performance"
FIG_DIR = _PROJ / "results" / "figures"
SEED = 42


@dataclass
class Item:
    holon_id: str
    tokens: int          # t(h): projection token cost
    value: float         # v(h): information value (sum of confidences)


def items_from_questions(questions=None) -> list:
    """Build knapsack items: tokens = projection cost, value = info content."""
    questions = questions or load_testset()
    items = []
    for q in questions:
        proj = q.question + " " + q.gold_answer
        tok = estimate_tokens(proj)
        val = sum(float(f["confidence"]) for f in q.facts) or 0.1
        items.append(Item(q.holon_id, max(1, tok), round(val, 4)))
    return items


# --------------------------------------------------------------------------- #
# Knapsack: greedy (1/2-approx) and exact DP
# --------------------------------------------------------------------------- #

def greedy_knapsack(items: list, L: int) -> tuple:
    """Modified ratio-greedy: better of (a) fill by value/token ratio and
    (b) the single most valuable item that fits. Guarantees >= OPT/2."""
    by_ratio = sorted(items, key=lambda it: (-(it.value / it.tokens), it.holon_id))
    chosen, used, val = [], 0, 0.0
    for it in by_ratio:
        if used + it.tokens <= L:
            chosen.append(it.holon_id)
            used += it.tokens
            val += it.value
    best_single = max((it for it in items if it.tokens <= L),
                      key=lambda it: it.value, default=None)
    if best_single is not None and best_single.value > val:
        return [best_single.holon_id], best_single.value
    return chosen, val


def dp_knapsack(items: list, L: int) -> float:
    """Exact 0/1 knapsack value via DP over integer token budget."""
    dp = [0.0] * (L + 1)
    # scale values to ints? values are floats; keep float DP (values additive).
    for it in items:
        w = it.tokens
        if w > L:
            continue
        for cap in range(L, w - 1, -1):
            cand = dp[cap - w] + it.value
            if cand > dp[cap]:
                dp[cap] = cand
    return dp[L]


def approximation_ratios(items: list, budgets: list) -> list:
    rows = []
    for L in budgets:
        _, gval = greedy_knapsack(items, L)
        opt = dp_knapsack(items, L)
        ratio = (gval / opt) if opt > 0 else 1.0
        rows.append({"budget": L, "greedy": round(gval, 3),
                     "optimal": round(opt, 3), "ratio": round(ratio, 4)})
    return rows


# --------------------------------------------------------------------------- #
# Latency: naive O(|V|) scan vs holon-based O(d*b)
# --------------------------------------------------------------------------- #

def latency_compare(repeats: int = 3) -> dict:
    """Naive retrieval scans every triple; holon-based touches only the
    boundary-relevant holons. Returns mean seconds for each."""
    g = load_corpus()
    triples = list(g)                                   # |V| ~ all triples
    rag = DualRAG()
    q = rag.questions[0]

    naive = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        # naive: full linear scan over every triple looking for the disease
        target = q.facts[0]["o"] if q.facts else ""
        _ = [t for t in triples if target in str(t[0]) or target in str(t[2])]
        naive.append(time.perf_counter() - t0)

    holon = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        _ = rag.context_A(q)                            # bounded: top-1 holon
        holon.append(time.perf_counter() - t0)

    return {
        "n_triples": len(triples),
        "naive_scan_s": min(naive),
        "holon_bounded_s": min(holon),
        "speedup": round(min(naive) / max(min(holon), 1e-9), 1),
    }


# --------------------------------------------------------------------------- #
# Scalability sweep: 100 / 500 / 1000 / 5000 holons
# --------------------------------------------------------------------------- #

def _replicate(questions: list, n: int) -> list:
    """Deterministically grow the question set to n by suffixing copies
    (synthetic replication; real 1000/5000-holon crawls are future work)."""
    out = []
    i = 0
    while len(out) < n:
        base = questions[i % len(questions)]
        clone = type(base)(**{**base.__dict__})
        clone.holon_id = f"{base.holon_id}__r{i // len(questions)}"
        clone.holon_uri = f"{base.holon_uri}__r{i // len(questions)}"
        out.append(clone)
        i += 1
    return out[:n]


def scalability_sweep(sizes=(100, 500, 1000, 5000)) -> list:
    base = load_testset()
    rows = []
    for n in sizes:
        qs = _replicate(base, n)
        t0 = time.perf_counter()
        rag = DualRAG(questions=qs)
        build_s = time.perf_counter() - t0

        sample = qs[: min(50, n)]
        tA = time.perf_counter()
        ctxA = [rag.context_A(q) for q in sample]
        a_s = (time.perf_counter() - tA) / len(sample)
        tB = time.perf_counter()
        ctxB = [rag.context_B(q) for q in sample]
        b_s = (time.perf_counter() - tB) / len(sample)

        rows.append({
            "n_holons": n,
            "index_build_s": round(build_s, 4),
            "A_retrieve_ms": round(a_s * 1000, 3),
            "B_retrieve_ms": round(b_s * 1000, 3),
            "A_avg_ctx_tokens": round(sum(c.context_tokens for c in ctxA) / len(ctxA), 1),
            "B_avg_ctx_tokens": round(sum(c.context_tokens for c in ctxB) / len(ctxB), 1),
        })
    return rows


def _write_and_plot(approx: list, lat: dict, sweep: list) -> None:
    PERF_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    with (PERF_DIR / "knapsack_approx.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["budget", "greedy", "optimal", "ratio"])
        w.writeheader()
        w.writerows(approx)
    with (PERF_DIR / "latency.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(lat.keys()))
        w.writeheader()
        w.writerow(lat)
    with (PERF_DIR / "scalability.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(sweep[0].keys()))
        w.writeheader()
        w.writerows(sweep)

    # Scalability figure: retrieval latency vs corpus size (A bounded vs B naive).
    ns = [r["n_holons"] for r in sweep]
    fig, ax = plt.subplots(1, 2, figsize=(10, 4))
    ax[0].plot(ns, [r["A_retrieve_ms"] for r in sweep], "o-", label="System A (holon-bounded)")
    ax[0].plot(ns, [r["B_retrieve_ms"] for r in sweep], "s-", label="System B (naive)")
    ax[0].set_xlabel("# holons"); ax[0].set_ylabel("retrieval latency (ms)")
    ax[0].set_title("Retrieval latency vs corpus size"); ax[0].legend()
    ax[1].plot(ns, [r["A_avg_ctx_tokens"] for r in sweep], "o-", label="System A")
    ax[1].plot(ns, [r["B_avg_ctx_tokens"] for r in sweep], "s-", label="System B")
    ax[1].set_xlabel("# holons"); ax[1].set_ylabel("avg context tokens")
    ax[1].set_title("Context size vs corpus size"); ax[1].legend()
    fig.tight_layout()
    fig.savefig(FIG_DIR / "scalability.png", dpi=120)
    plt.close(fig)


def main() -> None:
    items = items_from_questions()
    budgets = [100, 200, 400, 800, 1600]
    approx = approximation_ratios(items, budgets)
    lat = latency_compare()
    sweep = scalability_sweep()
    _write_and_plot(approx, lat, sweep)

    print("Knapsack greedy vs optimal (approximation ratio):")
    for r in approx:
        print(f"  L={r['budget']:>5}: greedy={r['greedy']:.2f} opt={r['optimal']:.2f} "
              f"ratio={r['ratio']:.3f}")
    print(f"\nLatency: naive scan {lat['naive_scan_s']*1000:.2f} ms over "
          f"{lat['n_triples']} triples vs holon-bounded "
          f"{lat['holon_bounded_s']*1000:.3f} ms  (speedup x{lat['speedup']})")
    print("\nScalability sweep:")
    for r in sweep:
        print(f"  n={r['n_holons']:>5}: A {r['A_retrieve_ms']:.3f} ms / "
              f"{r['A_avg_ctx_tokens']:.0f} tok | B {r['B_retrieve_ms']:.3f} ms / "
              f"{r['B_avg_ctx_tokens']:.0f} tok")
    print(f"\nWrote {PERF_DIR}/ and {FIG_DIR}/scalability.png")


if __name__ == "__main__":
    main()
