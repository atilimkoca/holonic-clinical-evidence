"""neo4j_loader.py — load the dual model into Neo4J and benchmark Cypher
(assignment §1.5 / Difficulty D: Neo4J vs RDF triple store).

Neo4J is optional infrastructure. This module degrades gracefully:

  * If the `neo4j` driver is installed AND a server is reachable (env vars
    NEO4J_URI / NEO4J_USER / NEO4J_PASS, defaults bolt://localhost:7687), it
    imports the holonic property-graph projection and times the Cypher
    equivalents of the SPARQL benchmark, writing results/neo4j_performance.csv.

  * Otherwise it still emits a runnable Cypher import script
    (results/neo4j/import_holonic.cypher) and a per-query Cypher file, and writes
    a status note — so the deliverable documents the Neo4J path without requiring
    a live database in the grading environment.

The property-graph projection: each reified evidence assertion becomes a typed
relationship (e.g. (:Drug)-[:TREATS {confidence, evidenceLevel, ...}]->(:Disease)),
which is exactly where an LPG is more natural than RDF reification — the headline
comparison the assignment asks for.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import time
from typing import Any, Optional

from . import config as C


def _read_holons() -> list[dict]:
    return json.loads((C.PROCESSED_DIR / "holons.json").read_text("utf-8"))


def _read_entities() -> dict:
    return json.loads((C.PROCESSED_DIR / "entities.json").read_text("utf-8"))


# --- Cypher generation (always runs) -----------------------------------------
def generate_cypher() -> str:
    """Emit a self-contained Cypher import script for the holonic property graph."""
    ent = _read_entities()
    holons = _read_holons()
    lines = [
        "// Holonic property-graph projection (Project 1, Model A -> LPG).",
        "// Run with: cypher-shell -f import_holonic.cypher",
        "CREATE CONSTRAINT disease_id IF NOT EXISTS FOR (d:Disease) REQUIRE d.id IS UNIQUE;",
        "CREATE CONSTRAINT drug_id IF NOT EXISTS FOR (x:Drug) REQUIRE x.id IS UNIQUE;",
        "CREATE CONSTRAINT holon_id IF NOT EXISTS FOR (h:Holon) REQUIRE h.id IS UNIQUE;",
        "",
    ]
    for slug, d in ent["diseases"].items():
        lab = d["label"].replace("'", "\\'")
        lines.append(f"MERGE (:Disease {{id:'{slug}', label:'{lab}', icd10:'{d['icd10']}', specialty:'{d['specialty']}'}});")
    for name, d in ent["drugs"].items():
        lines.append(f"MERGE (:Drug {{id:'{name}', atc:'{d['atc']}', class:'{d['drug_class']}'}});")
    lines.append("")
    for h in holons:
        if h["relation"] == "treats" and h["drug"]:
            lines.append(
                f"MATCH (x:Drug {{id:'{h['drug']}'}}),(d:Disease {{id:'{h['object']}'}}) "
                f"MERGE (x)-[:TREATS {{confidence:{h['confidence']}, evidenceLevel:'{h['evidence_level']}', "
                f"holon:'{h['id']}', recordedOn:'{h['recorded_on']}'}}]->(d);")
        elif h["relation"] == "causesSideEffect" and h["drug"]:
            lines.append(
                f"MATCH (x:Drug {{id:'{h['drug']}'}}),(s:Symptom {{id:'{h['object']}'}}) "
                f"MERGE (x)-[:CAUSES_SIDE_EFFECT {{confidence:{h['confidence']}, holon:'{h['id']}'}}]->(s);")
    return "\n".join(lines)


# Cypher equivalents of representative SPARQL benchmark queries.
CYPHER_QUERIES = {
    "S05_drugs_treating_htn":
        "MATCH (x:Drug)-[:TREATS]->(:Disease {id:'hypertension'}) RETURN x.id",
    "M01_treats_confidence":
        "MATCH (x:Drug)-[t:TREATS]->(d:Disease) RETURN x.id, d.id, t.confidence",
    "M03_high_conf_pairs":
        "MATCH (x:Drug)-[t:TREATS]->(d:Disease) WHERE t.confidence > 0.9 RETURN x.id, d.id",
    "C08_drug_breadth":
        "MATCH (x:Drug)-[t:TREATS]->(d:Disease) WHERE t.confidence >= 0.85 "
        "RETURN x.id, count(DISTINCT d) AS n ORDER BY n DESC LIMIT 5",
}


def _connect():
    try:
        import neo4j  # noqa: F401
        from neo4j import GraphDatabase
    except Exception:
        return None
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    pwd = os.environ.get("NEO4J_PASS", "neo4j")
    try:
        drv = GraphDatabase.driver(uri, auth=(user, pwd))
        drv.verify_connectivity()
        return drv
    except Exception as exc:                              # noqa: BLE001
        print(f"  Neo4J not reachable ({exc}); writing scripts only.")
        return None


def run(load: bool = True) -> dict[str, Any]:
    out_dir = C.RESULTS_DIR / "neo4j"
    out_dir.mkdir(parents=True, exist_ok=True)
    cypher = generate_cypher()
    (out_dir / "import_holonic.cypher").write_text(cypher, "utf-8")
    (out_dir / "benchmark_queries.cypher").write_text(
        "\n".join(f"// {k}\n{v};\n" for k, v in CYPHER_QUERIES.items()), "utf-8")

    drv = _connect() if load else None
    if drv is None:
        note = ("No Neo4J server was reachable during this run, so only the "
                "import + query Cypher scripts were generated under results/neo4j/. "
                "These scripts are portability artifacts outside the measured "
                "benchmark; the reported query timings are the per-query SPARQL "
                "timings (rdflib) in results/expressiveness.csv. To execute them: "
                "start Neo4J with n10s, set NEO4J_URI/USER/PASS, then "
                "`cypher-shell -f results/neo4j/import_holonic.cypher` and re-run "
                "this module.")
        (out_dir / "STATUS.md").write_text("# Neo4J status\n\n" + note + "\n", "utf-8")
        print("Neo4J loader: scripts generated; live DB not available (graceful skip).")
        return {"status": "scripts_only", "note": note}

    # live path
    rows = []
    with drv.session() as sess:
        for stmt in cypher.split(";\n"):
            stmt = stmt.strip()
            if stmt and not stmt.startswith("//"):
                sess.run(stmt)
        for qid, cy in CYPHER_QUERIES.items():
            t = time.perf_counter()
            res = sess.run(cy)
            n = sum(1 for _ in res)
            rows.append({"query": qid, "ms": round((time.perf_counter() - t) * 1000, 2), "rows": n})
    drv.close()
    with open(C.RESULTS_DIR / "neo4j_performance.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["query", "ms", "rows"]); w.writeheader(); w.writerows(rows)
    print(f"Neo4J loader: imported + benchmarked {len(rows)} Cypher queries.")
    return {"status": "ok", "rows": rows}


def main() -> None:
    ap = argparse.ArgumentParser(description="Load dual model into Neo4J (optional) + Cypher benchmark.")
    ap.add_argument("--no-load", action="store_true", help="Only generate Cypher scripts.")
    args = ap.parse_args()
    run(load=not args.no_load)


if __name__ == "__main__":
    main()
