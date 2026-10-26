"""databook_pipeline.py — DataBook-style provenance pipeline + end-to-end runner
(assignment §1.6, and the single entry point for rebuilding everything).

Runs the data-layer stages in order, recording a provenance chain (inputs,
outputs, duration, status, key metrics) for each, and — per the DataBook
requirement — documenting each data-producing step with a SHACL validation
report obtained from Project 2's validator (the cross-project integration check).

Stages:
  1. crawl        PubMed -> data/raw/articles/*.json        (cached; offline-safe)
  2. extract      raw -> data/processed/*.json
  3. transform    processed -> Model A (holonic) + Model B (flat)
  4. validate     SHACL-validate the holonic hand-off against Project 2 (Set A & B)
  5. benchmark    50-query expressiveness + information-preservation
  6. graph        holon-level topology, communities, homomorphism
  7. governance   centralized / federated / autonomous trade-offs
  8. neo4j        generate Cypher import + query scripts (live DB optional)

Usage:
  python -m project_1_crawling.src.databook_pipeline            # full run
  python -m project_1_crawling.src.databook_pipeline --offline  # no network
  python -m project_1_crawling.src.databook_pipeline --quick    # skip slow validate sample size
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from . import config as C
from . import crawler, entity_extractor, rdf_transformer, benchmark, graph_analysis, governance, neo4j_loader

# Project 2 validator (cross-project integration)
sys.path.insert(0, str(C.REPO_ROOT / "project_2_semantic" / "src"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()[:12] if path.exists() else ""


def _validate_handoff(sample: int = 15) -> dict[str, Any]:
    """SHACL-validate a sample of holonic hand-off holons against Project 2's
    Set A (boundary-aware) and Set B (flat) shapes."""
    try:
        from shacl_validator import validate_graph, load_ontology
        from rdflib import Graph
    except Exception as exc:                              # noqa: BLE001
        return {"status": "validator_unavailable", "error": str(exc)}

    ent = Graph()
    for f in glob.glob(str(C.RDF_HOLONIC_DIR / "entities" / "*.ttl")):
        ent.parse(f, format="turtle")
    ent.parse(str(C.RDF_HOLONIC_DIR / "relationships.ttl"), format="turtle")
    ont = load_ontology()
    shapes_a = str(C.REPO_ROOT / "project_2_semantic/shacl/shapes/boundary_aware")
    shapes_b = str(C.REPO_ROOT / "project_2_semantic/shacl/shapes/flat")

    files = sorted(glob.glob(str(C.RDF_HOLONIC_DIR / "clinical_questions" / "*.ttl")))[:sample]
    conform_a = conform_b = 0
    report_dir = C.RDF_DIR / "validation_reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    for i, f in enumerate(files):
        g = Graph(); g.parse(f, format="turtle")
        for t in ent:
            g.add(t)
        ca, rep_a, _ = validate_graph(g, shapes_a, "sh:Violation", ont_graph=ont)
        cb, _, _ = validate_graph(g, shapes_b, "sh:Violation", ont_graph=ont)
        conform_a += int(ca); conform_b += int(cb)
        if i == 0:                                       # keep one example report
            (report_dir / f"example_setA_report.ttl").write_text(rep_a, "utf-8")
    return {
        "status": "ok", "sampled": len(files),
        "setA_conforming": conform_a, "setB_conforming": conform_b,
        "setA_conformance_rate": round(conform_a / len(files), 3) if files else 0,
        "setB_conformance_rate": round(conform_b / len(files), 3) if files else 0,
    }


def run(offline: bool = False, validate_sample: int = 15) -> dict[str, Any]:
    C.ensure_dirs()
    chain: list[dict[str, Any]] = []

    def step(name: str, fn: Callable[[], Any], outputs: list[Path]) -> Any:
        t = time.perf_counter()
        status, metrics, err = "ok", {}, ""
        try:
            metrics = fn() or {}
        except Exception as exc:                          # noqa: BLE001
            status, err = "error", repr(exc)
        rec = {
            "step": name, "started": _now(),
            "duration_s": round(time.perf_counter() - t, 2),
            "status": status, "error": err,
            "outputs": [{"path": str(p.relative_to(C.PROJECT_ROOT)), "sha1": _sha(p),
                         "exists": p.exists()} for p in outputs],
            "metrics": metrics if isinstance(metrics, dict) else {},
        }
        chain.append(rec)
        print(f"[{status.upper():5}] {name}  ({rec['duration_s']}s)")
        if status == "error":
            print(f"        {err}")
        return metrics

    step("1_crawl", lambda: crawler.crawl(offline=offline),
         [C.RAW_DIR / "crawl_summary.json"])
    step("2_extract", lambda: entity_extractor.extract().get("stats"),
         [C.PROCESSED_DIR / "holons.json", C.PROCESSED_DIR / "entities.json"])
    step("3_transform", rdf_transformer.transform,
         [C.RDF_HOLONIC_DIR / "model_a.trig", C.RDF_FLAT_DIR / "model_b.ttl"])
    step("4_validate_handoff_project2", lambda: _validate_handoff(validate_sample),
         [C.RDF_DIR / "validation_reports" / "example_setA_report.ttl"])
    step("5_benchmark_expressiveness", benchmark.main,
         [C.RESULTS_DIR / "expressiveness.csv", C.RESULTS_DIR / "benchmark_summary.md"])
    step("6_graph_topology", graph_analysis.analyse,
         [C.RESULTS_DIR / "graph_metrics.json"])
    step("7_governance", governance.main,
         [C.RESULTS_DIR / "governance.json"])
    step("8_neo4j_scripts", lambda: neo4j_loader.run(load=True),
         [C.RESULTS_DIR / "neo4j" / "import_holonic.cypher"])

    provenance = {
        "pipeline": "BIL930 Project 1 — Holonic Data Layer DataBook",
        "generated": _now(),
        "offline": offline,
        "seed": C.SEED,
        "stages": chain,
        "ok": all(s["status"] == "ok" for s in chain),
    }
    (C.RESULTS_DIR / "databook_provenance.json").write_text(json.dumps(provenance, indent=2), "utf-8")
    _write_md(provenance)
    print(f"\nDataBook pipeline complete. All stages OK: {provenance['ok']}")
    return provenance


def _write_md(prov: dict) -> None:
    lines = [
        "# DataBook Provenance Chain — Project 1 Data Layer", "",
        f"Generated: {prov['generated']}  ·  offline={prov['offline']}  ·  seed={prov['seed']}",
        f"All stages OK: **{prov['ok']}**", "",
        "| # | Stage | Status | Duration (s) | Key output |",
        "|---|-------|--------|--------------|------------|",
    ]
    for s in prov["stages"]:
        out = s["outputs"][0]["path"] if s["outputs"] else ""
        lines.append(f"| {s['step'][0]} | {s['step'][2:]} | {s['status']} | {s['duration_s']} | `{out}` |")
    val = next((s for s in prov["stages"] if s["step"].startswith("4_")), None)
    if val and val["metrics"].get("status") == "ok":
        m = val["metrics"]
        lines += [
            "", "## Step-4 SHACL validation report (Project 2 integration)", "",
            f"- Sampled hand-off holons: {m['sampled']}",
            f"- Conforming to **Set A** (boundary-aware): {m['setA_conforming']} "
            f"({m['setA_conformance_rate']*100:.0f}%)",
            f"- Conforming to **Set B** (flat): {m['setB_conforming']} "
            f"({m['setB_conformance_rate']*100:.0f}%)",
            "", "Each data-producing stage is provenance-tracked with output SHA-1 "
            "checksums; the transform output is SHACL-validated against the "
            "downstream Project 2 shapes, documenting the hand-off contract.",
        ]
    (C.RESULTS_DIR / "databook.md").write_text("\n".join(lines), "utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="Run the full Project 1 DataBook pipeline.")
    ap.add_argument("--offline", action="store_true", help="No network; use cache/synthetic.")
    ap.add_argument("--validate-sample", type=int, default=15,
                    help="How many hand-off holons to SHACL-validate in step 4.")
    args = ap.parse_args()
    prov = run(offline=args.offline, validate_sample=args.validate_sample)
    sys.exit(0 if prov["ok"] else 1)


if __name__ == "__main__":
    main()
