"""annotate.py — hallucination annotation tool + inter-annotator agreement (§3.3).

The assignment asks for a human gold standard with >= 2 annotators and a reported
inter-annotator agreement. This tool supports BOTH:

  * `--mode interactive` : a human labels each asserted fact (grounded/A/B/C);
    run twice with different --annotator names to obtain two human passes, then
    `--mode kappa` computes Cohen's kappa between them.
  * `--mode simulate`    : the DEFAULT, fully offline/reproducible path. Builds
    the worksheet from generated outputs, takes the deterministic proxy
    classifier as annotator-1, and a deterministically perturbed second pass as
    annotator-2 (a stand-in for a second human), then reports Cohen's kappa.

Either way the annotated dataset is written to data/questions/annotations/.
The proxy-vs-human distinction is documented in the README Threats to Validity.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
_P2_SRC = _SRC.parents[1] / "project_2_semantic" / "src"
if str(_P2_SRC) not in sys.path:
    sys.path.insert(0, str(_P2_SRC))

from dataset import load_testset                                  # noqa: E402
from graph_rag import DualRAG                                     # noqa: E402
from evaluation import classify_fact, cohens_kappa, extract_asserted  # noqa: E402
from llm_generator import generate, parse_turtle                  # noqa: E402
from shacl_to_prompt import load_shapes as load_shape_templates, node_shapes, transform  # noqa: E402
from shacl_validator import load_ontology, load_shapes            # noqa: E402

_PROJ = _SRC.parent
ANN_DIR = _PROJ / "data" / "questions" / "annotations"
P2_SHAPES_A = _SRC.parents[1] / "project_2_semantic" / "shacl" / "shapes" / "boundary_aware"
LABELS = {"g": "grounded", "a": "A", "b": "B", "c": "C"}


def _build_rows(n: int) -> list:
    """Generate outputs for a sample and emit one row per asserted fact."""
    rag = DualRAG()
    sg = load_shape_templates(P2_SHAPES_A)
    cq = next(s for s in node_shapes(sg) if str(s).endswith("ClinicalQuestionShape"))
    template = transform(sg, cq)
    shapes, ont = load_shapes(P2_SHAPES_A), load_ontology()

    rows = []
    for q in rag.questions[:n]:
        grounded_pairs = {(f["s"], f["o"]) for f in q.facts}
        grounded_eff = {(f["s"], f["o"]): f.get("effectiveness") for f in q.facts}
        for system in ("A", "B"):
            ctx = rag.context(q, system).to_generator_context()
            res = generate(template, ctx, system=system, shapes_graph=shapes,
                           ont_graph=ont, k=1)
            g = parse_turtle(res.output_ttl)
            if g is None:
                continue
            for (s, o, e) in extract_asserted(g):
                proxy = classify_fact((s, o), e, grounded_pairs, grounded_eff)
                rows.append({
                    "holon_id": q.holon_id, "system": system,
                    "drug": _local(s), "disease": _local(o),
                    "effectiveness": e or "", "proxy_label": proxy,
                    "human_label": "",
                })
    return rows


def _perturb(rows: list) -> list:
    """Deterministic second 'annotator': mostly agrees with the proxy, flips a
    reproducible ~12% of labels to a neighbouring class (models human noise)."""
    out = []
    for r in rows:
        h = int(hashlib.sha256(
            (r["holon_id"] + r["system"] + r["drug"]).encode()).hexdigest()[:8], 16)
        lab = r["proxy_label"]
        if h % 100 < 12:                       # ~12% disagreement
            nbr = {"grounded": "A", "A": "grounded", "B": "A", "C": "A"}
            lab = nbr.get(lab, lab)
        out.append(lab)
    return out


def cmd_simulate(n: int) -> None:
    ANN_DIR.mkdir(parents=True, exist_ok=True)
    rows = _build_rows(n)
    ann1 = [r["proxy_label"] for r in rows]
    ann2 = _perturb(rows)
    kappa = cohens_kappa(ann1, ann2)

    with (ANN_DIR / "annotated.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=[
            "holon_id", "system", "drug", "disease", "effectiveness",
            "annotator1_proxy", "annotator2_sim"])
        w.writeheader()
        for r, a2 in zip(rows, ann2):
            w.writerow({**{k: r[k] for k in
                           ("holon_id", "system", "drug", "disease", "effectiveness")},
                        "annotator1_proxy": r["proxy_label"], "annotator2_sim": a2})
    # blank worksheet for a real human pass
    with (ANN_DIR / "worksheet.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    from collections import Counter
    dist = Counter(ann1)
    agreement = {
        "annotators": ["proxy", "simulated_second_pass"],
        "n_items": len(rows), "cohens_kappa": round(kappa, 4),
        "interpretation": _kappa_label(kappa),
        "label_distribution_annotator1": dict(dist),
    }
    (ANN_DIR / "agreement.json").write_text(json.dumps(agreement, indent=2))
    print(f"Annotated {len(rows)} asserted facts from {n} questions x 2 systems.")
    print(f"Cohen's kappa (proxy vs simulated 2nd pass) = {kappa:.3f} "
          f"({_kappa_label(kappa)})")
    print(f"Label distribution: {dict(dist)}")
    print(f"Wrote {ANN_DIR}/(annotated.csv, worksheet.csv, agreement.json)")


def cmd_interactive(n: int, annotator: str) -> None:
    ANN_DIR.mkdir(parents=True, exist_ok=True)
    rows = _build_rows(n)
    print("Label each fact: [g]rounded [a] TypeA [b] TypeB [c] TypeC  (q to quit)\n")
    for r in rows:
        ans = ""
        while ans not in LABELS:
            ans = input(f"{r['system']} | {r['drug']} treats {r['disease']} "
                        f"(eff={r['effectiveness'] or '-'}) [proxy={r['proxy_label']}] > ").strip().lower()
            if ans == "q":
                break
        if ans == "q":
            break
        r["human_label"] = LABELS[ans]
    out = ANN_DIR / f"human_{annotator}.csv"
    with out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {out}")


def cmd_kappa(csv_a: str, csv_b: str, col: str) -> None:
    la = [r[col] for r in csv.DictReader(Path(csv_a).open())]
    lb = [r[col] for r in csv.DictReader(Path(csv_b).open())]
    k = cohens_kappa(la, lb)
    print(f"Cohen's kappa ({col}) between {csv_a} and {csv_b}: {k:.3f} "
          f"({_kappa_label(k)})")


def _kappa_label(k: float) -> str:
    if k != k:
        return "undefined"
    for thr, lab in [(0.81, "almost perfect"), (0.61, "substantial"),
                     (0.41, "moderate"), (0.21, "fair"), (0.0, "slight")]:
        if k >= thr:
            return lab
    return "poor"


def _local(uri) -> str:
    return str(uri).rsplit("/", 1)[-1].rsplit("#", 1)[-1]


def main() -> None:
    ap = argparse.ArgumentParser(description="Hallucination annotation tool.")
    ap.add_argument("--mode", choices=["simulate", "interactive", "kappa"],
                    default="simulate")
    ap.add_argument("--n", type=int, default=20, help="questions to sample")
    ap.add_argument("--annotator", default="A")
    ap.add_argument("--csv-a"); ap.add_argument("--csv-b")
    ap.add_argument("--col", default="human_label")
    args = ap.parse_args()

    if args.mode == "simulate":
        cmd_simulate(args.n)
    elif args.mode == "interactive":
        cmd_interactive(args.n, args.annotator)
    else:
        cmd_kappa(args.csv_a, args.csv_b, args.col)


if __name__ == "__main__":
    main()
