"""Configuration loading and shared path constants for Project 1.

Centralises every filesystem path so the modules agree on where raw data,
processed data and RDF outputs live. All paths are resolved relative to
``project_1_crawling/`` regardless of the current working directory.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

# project_1_crawling/  (parents[1] of src/config.py)
PROJECT_ROOT: Path = Path(__file__).resolve().parents[1]
REPO_ROOT: Path = PROJECT_ROOT.parent                      # Final_Project/
SHARED_DIR: Path = REPO_ROOT / "shared"

CONFIG_PATH: Path = PROJECT_ROOT / "config" / "crawl_config.yaml"

DATA_DIR: Path = PROJECT_ROOT / "data"
RAW_DIR: Path = DATA_DIR / "raw"
PROCESSED_DIR: Path = DATA_DIR / "processed"
RDF_DIR: Path = DATA_DIR / "rdf"
RDF_HOLONIC_DIR: Path = RDF_DIR / "holonic"
RDF_FLAT_DIR: Path = RDF_DIR / "flat"

RESULTS_DIR: Path = PROJECT_ROOT / "results"
FIGURES_DIR: Path = RESULTS_DIR / "figures"
QUERIES_DIR: Path = PROJECT_ROOT / "queries"

# Fixed "crawl date" used as holon:recordedOn for every assertion. Chosen to be
# later than any source publication date so the data is temporally consistent
# (Project 2's T3 check requires recordedOn >= source publicationDate).
CRAWL_DATE: str = "2025-06-01"

SEED: int = 42


@lru_cache(maxsize=1)
def load_config() -> dict[str, Any]:
    """Parse and cache crawl_config.yaml."""
    with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def ensure_dirs() -> None:
    """Create all output directories (idempotent)."""
    for d in (
        RAW_DIR, PROCESSED_DIR, RDF_DIR, RDF_HOLONIC_DIR, RDF_FLAT_DIR,
        RESULTS_DIR, FIGURES_DIR,
        RDF_HOLONIC_DIR / "clinical_questions",
        RDF_HOLONIC_DIR / "entities",
        RAW_DIR / "articles",
    ):
        d.mkdir(parents=True, exist_ok=True)
