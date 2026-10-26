"""crawler.py — gather a per-disease pool of evidence articles.

For every disease in ``crawl_config.yaml`` we issue one relevance-sorted PubMed
search (therapy-focused) and fetch the resulting article records. The pool is
written to ``data/raw/articles/<slug>.json`` and is the *only* network-dependent
step in the pipeline; everything downstream reads these cached pools, so the RDF
can be rebuilt deterministically and offline.

If the network is unavailable (or a search returns nothing) and
``allow_synthetic_fallback`` is set, a deterministic synthetic article pool is
generated from the curated config so the pipeline always yields a complete,
reproducible dataset. Synthetic records are flagged (``"synthetic": true``) and
counted in the crawl summary so the report can disclose them honestly.
"""
from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path
from typing import Any

from . import config as C
from .pubmed_client import Article, PubMedClient


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


# Publication types cycled through when fabricating offline fallback articles,
# chosen so the evidence-level distribution mirrors a real therapy search.
_FALLBACK_PTYPES = [
    ["Meta-Analysis"], ["Systematic Review"], ["Randomized Controlled Trial"],
    ["Randomized Controlled Trial"], ["Comparative Study"], ["Clinical Trial"],
    ["Observational Study"], ["Review"],
]


def _synthetic_pool(disease: dict[str, Any], drugs_cfg: dict, n: int, rng: random.Random) -> list[Article]:
    """Deterministic fabricated article pool for offline reproducibility."""
    pool: list[Article] = []
    drug_names = disease.get("drugs") or list(drugs_cfg.keys())[:3]
    for i in range(n):
        ptypes = _FALLBACK_PTYPES[i % len(_FALLBACK_PTYPES)]
        year = 2012 + (i % 12)
        drug = drug_names[i % len(drug_names)] if drug_names else "therapy"
        pmid = f"SYN{abs(hash((disease['name'], i))) % 9000000 + 1000000}"
        pool.append(Article(
            pmid=pmid,
            title=f"{ptypes[0]} of {drug} for {disease['name']}",
            abstract=(f"This {ptypes[0].lower()} evaluated {drug} in patients with "
                      f"{disease['name']}. Treatment was associated with improved "
                      f"clinical outcomes relative to comparator."),
            pub_date=f"{year}-{rng.randint(1,12):02d}-15",
            publication_types=list(ptypes),
            mesh_descriptors=[disease["name"]],
            chemicals=[d.replace('_', ' ').title() for d in drug_names],
            journal="Synthetic Evidence Journal",
            authors=["A. Author", "B. Researcher"],
        ))
    return pool


def crawl(offline: bool = False, refresh: bool = False) -> dict[str, Any]:
    """Crawl (or replay from cache) all disease article pools.

    Returns a summary dict; also writes ``data/raw/crawl_summary.json``.
    """
    cfg = C.load_config()
    crawl_cfg = cfg["crawl"]
    C.ensure_dirs()
    rng = random.Random(crawl_cfg.get("seed", C.SEED))

    client = PubMedClient(
        base_url=crawl_cfg["base_url"],
        cache_dir=C.PROJECT_ROOT / crawl_cfg["cache_dir"],
        email=crawl_cfg.get("email", ""),
        tool_name=crawl_cfg.get("tool_name", "BIL930"),
        user_agent=crawl_cfg.get("user_agent", "BIL930/1.0"),
        delay_seconds=crawl_cfg.get("delay_seconds", 0.4),
        max_retries=crawl_cfg.get("max_retries", 3),
        timeout_seconds=crawl_cfg.get("timeout_seconds", 20),
        offline=offline,
    )

    retmax = crawl_cfg.get("retmax_per_query", 12)
    allow_synth = crawl_cfg.get("allow_synthetic_fallback", True)
    articles_dir = C.RAW_DIR / "articles"

    summary = {
        "diseases": 0, "real_pools": 0, "synthetic_pools": 0,
        "total_articles": 0, "real_articles": 0, "synthetic_articles": 0,
        "network_calls": 0, "cache_hits": 0, "per_disease": {},
    }

    for disease in cfg["diseases"]:
        slug = slugify(disease["name"])
        out_path = articles_dir / f"{slug}.json"
        if out_path.exists() and not refresh:
            pool = [Article.from_dict(a) for a in json.loads(out_path.read_text("utf-8"))["articles"]]
            is_synth = json.loads(out_path.read_text("utf-8")).get("synthetic", False)
        else:
            term = f'{disease["mesh"]}[mesh] AND (drug therapy[sh] OR therapy[sh])'
            pmids = client.esearch(term, retmax=retmax)
            pool = client.efetch(pmids)
            is_synth = False
            if not pool and allow_synth:
                pool = _synthetic_pool(disease, cfg["drugs"], retmax, rng)
                is_synth = True
            out_path.write_text(json.dumps(
                {"disease": disease["name"], "slug": slug, "synthetic": is_synth,
                 "articles": [a.to_dict() for a in pool]},
                indent=2), encoding="utf-8")

        summary["diseases"] += 1
        summary["total_articles"] += len(pool)
        if is_synth:
            summary["synthetic_pools"] += 1
            summary["synthetic_articles"] += len(pool)
        else:
            summary["real_pools"] += 1
            summary["real_articles"] += len(pool)
        summary["per_disease"][slug] = {"n": len(pool), "synthetic": is_synth}
        flag = " [synthetic]" if is_synth else ""
        print(f"  {disease['name']:<42} {len(pool):>3} articles{flag}")

    summary["network_calls"] = client.network_calls
    summary["cache_hits"] = client.cache_hits
    (C.RAW_DIR / "crawl_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nCrawl done: {summary['diseases']} diseases, "
          f"{summary['total_articles']} articles "
          f"({summary['real_articles']} real / {summary['synthetic_articles']} synthetic), "
          f"{summary['network_calls']} network calls, {summary['cache_hits']} cache hits.")
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description="Crawl per-disease evidence pools from PubMed.")
    ap.add_argument("--offline", action="store_true",
                    help="Never hit the network; use cache or synthetic fallback only.")
    ap.add_argument("--refresh", action="store_true",
                    help="Re-fetch even if a per-disease pool file already exists.")
    args = ap.parse_args()
    crawl(offline=args.offline, refresh=args.refresh)


if __name__ == "__main__":
    main()
