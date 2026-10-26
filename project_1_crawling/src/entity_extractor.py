"""entity_extractor.py — turn raw article pools into a normalised knowledge model.

Reads ``config`` + ``data/raw/articles/*.json`` and produces three JSON files in
``data/processed/``:

  entities.json   — diseases, drugs, symptoms, specialties, sources, authors
  holons.json     — clinical-question holons (one per disease x question facet)
  hierarchy.json  — the 3-level holon containment tree
                    (Specialty -> Disease -> ClinicalQuestion), for Difficulty A

Determinism: every fabricated value (drug approval dates, disease first-described
dates, confidence jitter) is derived by hashing stable keys with a fixed seed,
so re-running yields byte-identical output without any randomness.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from typing import Any, Optional

from . import config as C
from .crawler import slugify


# --- deterministic helpers ---------------------------------------------------
def _h(*parts: str) -> int:
    """Stable non-negative integer hash of the given parts (seeded)."""
    key = f"{C.SEED}:" + "|".join(parts)
    return int(hashlib.sha1(key.encode("utf-8")).hexdigest(), 16)


def _date_in(start_year: int, end_year: int, *key: str) -> str:
    span = end_year - start_year
    y = start_year + _h(*key) % (span + 1)
    m = 1 + _h("m", *key) % 12
    d = 1 + _h("d", *key) % 28
    return f"{y:04d}-{m:02d}-{d:02d}"


def _evidence_level(pub_types: list[str], ev_cfg: dict) -> dict[str, Any]:
    """Map an article's publication types to the strongest evidence level."""
    best: Optional[dict] = None
    for pt in pub_types:
        info = ev_cfg.get(pt)
        if info and (best is None or info["score"] > best["score"]):
            best = info
    return best or ev_cfg["_default"]


def _confidence(base_score: float, *key: str) -> float:
    """Evidence score nudged by a small deterministic jitter, clamped to [0,1]."""
    jitter = (_h("conf", *key) % 7 - 3) / 100.0      # -0.03 .. +0.03
    return round(min(1.0, max(0.0, base_score + jitter)), 2)


def _first_sentences(text: str, n: int = 2) -> str:
    if not text:
        return ""
    parts = text.replace("\n", " ").split(". ")
    out = ". ".join(parts[:n]).strip()
    if out and not out.endswith("."):
        out += "."
    return out


# --- main extraction ---------------------------------------------------------
def extract() -> dict[str, Any]:
    cfg = C.load_config()
    C.ensure_dirs()
    ev_cfg = cfg["evidence_levels"]
    drugs_cfg = cfg["drugs"]
    symptoms_cfg = cfg["symptoms"]
    specialties_cfg = cfg["specialties"]
    templates = {t["id"]: t for t in cfg["question_templates"]}
    articles_dir = C.RAW_DIR / "articles"

    entities: dict[str, Any] = {
        "diseases": {}, "drugs": {}, "symptoms": {}, "specialties": {},
        "sources": {}, "authors": {},
    }
    holons: list[dict[str, Any]] = []
    hierarchy: dict[str, dict[str, Any]] = {}

    # specialties
    for name, desc in specialties_cfg.items():
        entities["specialties"][name] = {"label": name, "description": desc}
        hierarchy.setdefault(name, {"holon_id": f"spec_{slugify(name)}", "diseases": {}})

    # symptoms
    for slug, label in symptoms_cfg.items():
        entities["symptoms"][slug] = {"label": label}

    # drugs (approval date deterministic, 1985-2015)
    for name, meta in drugs_cfg.items():
        entities["drugs"][name] = {
            "label": name.replace("_", " ").title(),
            "atc": meta["atc"],
            "drug_class": meta["class"],
            "approval_date": _date_in(1985, 2015, "approval", name),
        }

    for disease in cfg["diseases"]:
        dslug = slugify(disease["name"])
        specialty = disease["specialty"]
        # disease entity (first-described 1900-1980 => always before drug approval)
        entities["diseases"][dslug] = {
            "label": disease["name"],
            "icd10": disease["icd10"],
            "mesh": disease["mesh"],
            "specialty": specialty,
            "first_described_date": _date_in(1900, 1980, "described", dslug),
            "symptoms": disease.get("symptoms", []),
            "drugs": disease.get("drugs", []),
        }
        disease_holon_id = f"dis_{dslug}"
        hierarchy[specialty]["diseases"][dslug] = {
            "holon_id": disease_holon_id, "questions": [],
        }

        # load this disease's article pool
        pool_path = articles_dir / f"{dslug}.json"
        pool = json.loads(pool_path.read_text("utf-8"))["articles"] if pool_path.exists() else []
        # register sources + authors
        for art in pool:
            pmid = art["pmid"]
            if pmid not in entities["sources"]:
                lvl = _evidence_level(art["publication_types"], ev_cfg)
                entities["sources"][pmid] = {
                    "pmid": pmid,
                    "title": art["title"][:300],
                    "journal": art["journal"],
                    "source_class": lvl["source_class"],
                    "evidence_level": lvl["level"],
                    "score": lvl["score"],
                    "publication_date": art["pub_date"] or "2015-01-01",
                    "publication_types": art["publication_types"],
                }
                for au in art["authors"]:
                    aslug = slugify(au)
                    if aslug:
                        entities["authors"].setdefault(aslug, {"label": au})

        drugs = disease.get("drugs", [])
        # partition the pool into one slice per facet (deterministic, contiguous)
        n_facets = len(cfg["question_templates"])
        slice_sz = max(1, len(pool) // n_facets) if pool else 0

        for fi, tmpl in enumerate(cfg["question_templates"]):
            facet = tmpl["id"]
            drug = drugs[0] if drugs else None
            citations = pool[fi * slice_sz:(fi + 1) * slice_sz] or pool[:cfg["crawl"]["max_articles_per_holon"]]
            citations = citations[:cfg["crawl"]["max_articles_per_holon"]]
            if not citations:
                continue
            # primary evidence = strongest-scoring citation
            prim = max(
                citations,
                key=lambda a: _evidence_level(a["publication_types"], ev_cfg)["score"],
            )
            prim_lvl = _evidence_level(prim["publication_types"], ev_cfg)
            qid = f"q_{dslug}_{facet}"

            # relation + object depend on the facet
            relation: Optional[str] = None
            obj: Optional[str] = None
            obj_kind: Optional[str] = None
            if facet in ("treatment", "efficacy") and drug:
                relation, obj, obj_kind = "treats", dslug, "disease"
            elif facet == "safety" and drug:
                sym = disease.get("symptoms") or ["fatigue"]
                relation, obj, obj_kind = "causesSideEffect", sym[0], "symptom"

            qtext = tmpl["text"].format(
                disease=disease["name"],
                drug=(drug.replace("_", " ") if drug else "available therapies"),
            )
            answer = _first_sentences(prim["abstract"]) or (
                f"Evidence from {len(citations)} sources informs management of "
                f"{disease['name']}.")
            conf = _confidence(prim_lvl["score"], qid, prim["pmid"])
            threshold = 0.50
            # recordedOn must not precede any cited source's publication date
            # (Project 2's T3 temporal check); take the latest of crawl date and
            # citation publication dates.
            pub_dates = [c["pub_date"] for c in citations if c.get("pub_date")]
            recorded_on = max([C.CRAWL_DATE] + pub_dates)
            # An assertion is only labelled "effective" when its confidence clears
            # the holon's quality threshold; weaker evidence is "inconclusive".
            # This keeps Project 1's BASE data semantically consistent (no T4);
            # Project 2 injects T4 defects into its own corpus deliberately.
            effectiveness = "effective" if conf >= threshold else "inconclusive"

            holon = {
                "id": qid,
                "type": "ClinicalQuestionHolon",
                "facet": facet,
                "disease": dslug,
                "specialty": specialty,
                "drug": drug,
                "drug_class": drugs_cfg[drug]["class"] if drug else None,
                "relation": relation,
                "object": obj,
                "object_kind": obj_kind,
                "question_text": qtext,
                "answer_text": answer,
                "citations": [c["pmid"] for c in citations],
                "primary_pmid": prim["pmid"],
                "evidence_level": prim_lvl["level"],
                "confidence": conf,
                "effectiveness": effectiveness,
                "recorded_on": recorded_on,
                "narrative": (f"Summarises evidence on managing {disease['name']}"
                              + (f" with {drug.replace('_',' ')}" if drug else "") + "."),
                "summary_confidence": conf,
                "aggregate_confidence": round(
                    sum(_evidence_level(c["publication_types"], ev_cfg)["score"]
                        for c in citations) / len(citations), 2),
                "evidence_quality_threshold": 0.50,
                "parent_disease_holon": disease_holon_id,
            }
            holons.append(holon)
            hierarchy[specialty]["diseases"][dslug]["questions"].append(qid)

    stats = {
        "n_holons": len(holons),
        "n_diseases": len(entities["diseases"]),
        "n_drugs": len(entities["drugs"]),
        "n_symptoms": len(entities["symptoms"]),
        "n_sources": len(entities["sources"]),
        "n_authors": len(entities["authors"]),
        "n_specialties": len(entities["specialties"]),
        "n_entities_total": sum(len(entities[k]) for k in
                                ("diseases", "drugs", "symptoms", "sources", "authors", "specialties")),
    }

    (C.PROCESSED_DIR / "entities.json").write_text(json.dumps(entities, indent=1), "utf-8")
    (C.PROCESSED_DIR / "holons.json").write_text(json.dumps(holons, indent=1), "utf-8")
    (C.PROCESSED_DIR / "hierarchy.json").write_text(json.dumps(hierarchy, indent=1), "utf-8")
    (C.PROCESSED_DIR / "extract_stats.json").write_text(json.dumps(stats, indent=2), "utf-8")

    print("Entity extraction complete:")
    for k, v in stats.items():
        print(f"  {k:<20} {v}")
    return {"entities": entities, "holons": holons, "hierarchy": hierarchy, "stats": stats}


def main() -> None:
    argparse.ArgumentParser(description="Normalise raw article pools into entities + holons.").parse_args()
    extract()


if __name__ == "__main__":
    main()
