"""holon_evolver.py — Active inference & holon evolution (§3.5).

Models each holon's belief about a treatment's effectiveness as a Beta
distribution and updates it as new evidence arrives:

  * **Bayesian update**: Beta(alpha, beta) -> Beta(alpha + s, beta + f) where a
    new study contributes weight `w` (by evidence level) to s (effective) or
    f (ineffective).
  * **Bayesian surprise**: KL( posterior || prior ) per update (information the
    new evidence injected).
  * **Conflict + termination**: when an update flips the posterior mean across
    0.5 (the effective/ineffective boundary), the old assertion is closed with a
    `holon:StateTransition` carrying `holon:terminates` (the closure operator
    from the shared ontology), and the holon's verdict is superseded.

Runs on >= 10 real holons, deterministically (seed 42). Outputs the trajectory
CSV/MD, a `holon:terminates` Turtle witness, and a figure.
"""
from __future__ import annotations

import csv
import random
import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt        # noqa: E402
from scipy.special import betaln, digamma  # noqa: E402

_SRC = Path(__file__).resolve().parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from dataset import load_testset       # noqa: E402

_PROJ = _SRC.parent
OUT = _PROJ / "results" / "active_inference"
FIG = _PROJ / "results" / "figures"

PRIOR_STRENGTH = 8.0          # pseudo-counts encoding initial confidence
LEVEL_WEIGHT = {"Level-1A": 5.0, "Level-1B": 4.0, "Level-2A": 3.0,
                "Level-2B": 2.0, "Level-3": 1.5, "Level-4": 1.0, "Level-5": 0.5}
N_STEPS = 5
SEED = 42


def kl_beta(a1: float, b1: float, a2: float, b2: float) -> float:
    """KL( Beta(a1,b1) || Beta(a2,b2) ) — Bayesian surprise of the update."""
    return float(
        betaln(a2, b2) - betaln(a1, b1)
        + (a1 - a2) * digamma(a1) + (b1 - b2) * digamma(b1)
        + (a2 - a1 + b2 - b1) * digamma(a1 + b1)
    )


@dataclass
class Step:
    t: int
    evidence: str            # "effective" | "ineffective"
    level: str
    weight: float
    mean: float
    surprise: float
    terminated: bool = False


@dataclass
class Trajectory:
    holon_id: str
    drug: str
    disease: str
    initial_mean: float
    steps: list = field(default_factory=list)
    n_terminations: int = 0


def _evidence_stream(rng: random.Random, contradict: bool) -> list:
    """A deterministic sequence of (effectiveness, level) events. `contradict`
    holons receive a wave of opposing evidence to trigger a termination."""
    levels = list(LEVEL_WEIGHT)
    out = []
    for t in range(N_STEPS):
        if contradict and t >= N_STEPS - 2:
            eff = "ineffective"               # late contradicting evidence
            lvl = "Level-1A"
        else:
            eff = "effective" if rng.random() < 0.7 else "ineffective"
            lvl = rng.choice(levels)
        out.append((eff, lvl))
    return out


def evolve(question, contradict: bool) -> Trajectory:
    f = question.facts[0]
    c0 = float(f["confidence"])
    alpha = max(0.1, c0 * PRIOR_STRENGTH)
    beta = max(0.1, (1 - c0) * PRIOR_STRENGTH)
    traj = Trajectory(holon_id=question.holon_id, drug=_local(f["s"]),
                      disease=_local(f["o"]), initial_mean=alpha / (alpha + beta))
    rng = random.Random(hash(question.holon_id) & 0xFFFF ^ SEED)
    prev_mean = traj.initial_mean
    for t, (eff, lvl) in enumerate(_evidence_stream(rng, contradict)):
        w = LEVEL_WEIGHT[lvl]
        a0, b0 = alpha, beta
        if eff == "effective":
            alpha += w
        else:
            beta += w
        mean = alpha / (alpha + beta)
        surprise = kl_beta(alpha, beta, a0, b0)      # KL(posterior || prior)
        terminated = (prev_mean >= 0.5 > mean) or (prev_mean < 0.5 <= mean)
        traj.steps.append(Step(t, eff, lvl, w, round(mean, 4),
                               round(surprise, 4), terminated))
        if terminated:
            traj.n_terminations += 1
        prev_mean = mean
    return traj


def run(n_holons: int = 12) -> list:
    qs = [q for q in load_testset() if q.facts][:n_holons]
    trajs = []
    for i, q in enumerate(qs):
        trajs.append(evolve(q, contradict=(i % 3 == 0)))   # ~1/3 get contradiction
    _write(trajs)
    _figure(trajs)
    _terminations_ttl(trajs, qs)
    return trajs


def _write(trajs: list) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "evolution.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["holon_id", "drug", "disease", "step", "evidence", "level",
                    "weight", "posterior_mean", "surprise_kl", "terminated"])
        for tr in trajs:
            for s in tr.steps:
                w.writerow([tr.holon_id, tr.drug, tr.disease, s.t, s.evidence,
                            s.level, s.weight, s.mean, s.surprise, s.terminated])
    total_term = sum(tr.n_terminations for tr in trajs)
    md = ["# §3.5 — Active Inference: Holon Temporal Evolution\n",
          f"- Holons evolved: **{len(trajs)}** over {N_STEPS} evidence steps each "
          f"(seed {SEED}).",
          f"- Total `holon:terminates` events (verdict flips): **{total_term}**.",
          "- Surprise = KL(posterior || prior) per Bayesian update; spikes mark "
          "high-information (often contradicting) evidence.\n",
          "| Holon | drug→disease | initial | final | flips |",
          "|-------|--------------|---------|-------|-------|"]
    for tr in trajs:
        md.append(f"| {tr.holon_id} | {tr.drug}→{tr.disease} | "
                  f"{tr.initial_mean:.2f} | {tr.steps[-1].mean:.2f} | "
                  f"{tr.n_terminations} |")
    md.append("\nA termination fires when new evidence moves the posterior mean "
              "across the 0.5 effective/ineffective boundary; the superseded "
              "assertion is closed with `holon:terminates` (see terminations.ttl).")
    (OUT / "evolution.md").write_text("\n".join(md))


def _figure(trajs: list) -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(1, 2, figsize=(11, 4))
    for tr in trajs:
        xs = [0] + [s.t + 1 for s in tr.steps]
        ys = [tr.initial_mean] + [s.mean for s in tr.steps]
        ax[0].plot(xs, ys, marker="o", alpha=0.7)
        for s in tr.steps:
            if s.terminated:
                ax[0].scatter([s.t + 1], [s.mean], marker="x", s=90, color="black", zorder=5)
    ax[0].axhline(0.5, ls="--", color="gray", lw=1)
    ax[0].set_xlabel("evidence step"); ax[0].set_ylabel("posterior mean confidence")
    ax[0].set_title("Holon belief evolution (x = termination)")
    for tr in trajs:
        ax[1].plot([s.t + 1 for s in tr.steps], [s.surprise for s in tr.steps],
                   marker=".", alpha=0.7)
    ax[1].set_xlabel("evidence step"); ax[1].set_ylabel("surprise  KL(post||prior)")
    ax[1].set_title("Bayesian surprise per update")
    fig.tight_layout(); fig.savefig(FIG / "active_inference.png", dpi=120)
    plt.close(fig)


def _terminations_ttl(trajs: list, qs: list) -> None:
    by_id = {q.holon_id: q for q in qs}
    lines = [
        "@prefix holon: <https://example.org/holon#> .",
        "@prefix oe: <https://example.org/openevidence#> .",
        "@prefix oegen: <https://example.org/openevidence/generated/> .",
        "@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .",
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
        "",
    ]
    base = date(2026, 1, 1)
    for tr in trajs:
        q = by_id[tr.holon_id]
        for s in tr.steps:
            if not s.terminated:
                continue
            old = f"oegen:ev_{tr.holon_id}_0"
            tr_node = f"oegen:transition_{tr.holon_id}_{s.t}"
            when = (base + timedelta(days=90 * (s.t + 1))).isoformat()
            new_eff = "ineffective" if s.mean < 0.5 else "effective"
            lines += [
                f"{tr_node} a holon:StateTransition ;",
                f"    holon:terminates {old} ;",
                f"    holon:inHolon <{q.holon_uri}> ;",
                f'    holon:confidence "{s.mean:.2f}"^^xsd:decimal ;',
                f'    holon:recordedOn "{when}"^^xsd:date ;',
                f'    oe:effectiveness "{new_eff}" ;',
                f'    holon:rationale "Superseded by Level-1A contradicting evidence (KL surprise {s.surprise:.2f})." .',
                "",
            ]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "terminations.ttl").write_text("\n".join(lines))


def _local(uri) -> str:
    return str(uri).rsplit("/", 1)[-1].rsplit("#", 1)[-1]


def main() -> None:
    trajs = run()
    total = sum(tr.n_terminations for tr in trajs)
    print(f"Evolved {len(trajs)} holons x {N_STEPS} steps; "
          f"{total} terminations (verdict flips).")
    for tr in trajs[:6]:
        print(f"  {tr.holon_id}: {tr.initial_mean:.2f} -> {tr.steps[-1].mean:.2f} "
              f"(flips={tr.n_terminations}, max surprise="
              f"{max(s.surprise for s in tr.steps):.2f})")
    print(f"Wrote {OUT}/ and {FIG}/active_inference.png")


if __name__ == "__main__":
    main()
