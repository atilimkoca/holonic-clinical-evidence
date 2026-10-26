"""run_all.py — convenience entry point. Delegates to the DataBook pipeline,
which runs every data-layer stage with provenance tracking.

    python -m project_1_crawling.src.run_all            # full run (uses cached crawl)
    python -m project_1_crawling.src.run_all --offline  # never touch the network
"""
from __future__ import annotations

from .databook_pipeline import main

if __name__ == "__main__":
    main()
