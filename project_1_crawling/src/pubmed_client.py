"""pubmed_client.py — a minimal, polite NCBI E-utilities client.

Implements only the two endpoints we need (esearch + efetch) with:
  * on-disk response caching (so a crawl is reproducible and offline-replayable),
  * rate limiting (NCBI allows 3 requests/sec without an API key),
  * bounded retries with exponential backoff,
  * defensive XML parsing into plain dicts.

Caching is keyed by a hash of the request URL; cached responses are committed
with the project so graders can rebuild the RDF without network access.
"""
from __future__ import annotations

import hashlib
import json
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class Article:
    """A normalised PubMed article record."""
    pmid: str
    title: str
    abstract: str
    pub_date: str                       # ISO yyyy-mm-dd (best-effort)
    publication_types: list[str] = field(default_factory=list)
    mesh_descriptors: list[str] = field(default_factory=list)
    chemicals: list[str] = field(default_factory=list)
    journal: str = ""
    authors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pmid": self.pmid, "title": self.title, "abstract": self.abstract,
            "pub_date": self.pub_date, "publication_types": self.publication_types,
            "mesh_descriptors": self.mesh_descriptors, "chemicals": self.chemicals,
            "journal": self.journal, "authors": self.authors,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Article":
        return cls(**d)


_MONTHS = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05", "jun": "06",
    "jul": "07", "aug": "08", "sep": "09", "oct": "10", "nov": "11", "dec": "12",
}


class PubMedClient:
    """Cached, rate-limited E-utilities client."""

    def __init__(
        self,
        base_url: str,
        cache_dir: Path,
        email: str = "",
        tool_name: str = "BIL930",
        user_agent: str = "BIL930/1.0",
        delay_seconds: float = 0.4,
        max_retries: int = 3,
        timeout_seconds: int = 20,
        offline: bool = False,
    ) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.email = email
        self.tool_name = tool_name
        self.user_agent = user_agent
        self.delay_seconds = delay_seconds
        self.max_retries = max_retries
        self.timeout_seconds = timeout_seconds
        self.offline = offline
        self._last_request_ts = 0.0
        self.network_calls = 0
        self.cache_hits = 0

    # -- low-level ----------------------------------------------------------
    def _cache_path(self, url: str) -> Path:
        h = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
        return self.cache_dir / f"{h}.txt"

    def _throttle(self) -> None:
        elapsed = time.time() - self._last_request_ts
        if elapsed < self.delay_seconds:
            time.sleep(self.delay_seconds - elapsed)
        self._last_request_ts = time.time()

    def _get(self, endpoint: str, params: dict[str, Any]) -> Optional[str]:
        """Return raw response text, using cache when available.

        Returns None if the resource cannot be fetched (offline / network error)
        and is not cached, letting the caller fall back gracefully.
        """
        params = {**params, "tool": self.tool_name, "email": self.email}
        url = self.base_url + endpoint + "?" + urllib.parse.urlencode(params)
        cache_path = self._cache_path(url)
        if cache_path.exists():
            self.cache_hits += 1
            return cache_path.read_text(encoding="utf-8")
        if self.offline:
            return None

        req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        last_err: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                self._throttle()
                with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                    text = resp.read().decode("utf-8", errors="replace")
                self.network_calls += 1
                cache_path.write_text(text, encoding="utf-8")
                return text
            except Exception as exc:                       # noqa: BLE001
                last_err = exc
                time.sleep(self.delay_seconds * (2 ** attempt))
        print(f"  ! PubMed request failed ({endpoint}): {last_err}")
        return None

    # -- endpoints ----------------------------------------------------------
    def esearch(self, term: str, retmax: int = 12) -> list[str]:
        """Return a list of PMIDs for a query term (relevance-sorted)."""
        text = self._get("esearch.fcgi", {
            "db": "pubmed", "term": term, "retmax": retmax,
            "retmode": "json", "sort": "relevance",
        })
        if not text:
            return []
        try:
            data = json.loads(text)
            return list(data["esearchresult"]["idlist"])
        except (json.JSONDecodeError, KeyError):
            return []

    def efetch(self, pmids: list[str]) -> list[Article]:
        """Fetch full records for a batch of PMIDs."""
        if not pmids:
            return []
        text = self._get("efetch.fcgi", {
            "db": "pubmed", "id": ",".join(pmids), "retmode": "xml",
        })
        if not text:
            return []
        try:
            root = ET.fromstring(text)
        except ET.ParseError:
            return []
        return [self._parse_article(a) for a in root.findall(".//PubmedArticle")]

    # -- parsing ------------------------------------------------------------
    @staticmethod
    def _parse_date(art: ET.Element) -> str:
        pd = art.find(".//Article//Journal//JournalIssue//PubDate")
        if pd is None:
            pd = art.find(".//PubDate")
        year = month = day = None
        if pd is not None:
            year = pd.findtext("Year")
            month = pd.findtext("Month")
            day = pd.findtext("Day")
            if year is None:
                medline = pd.findtext("MedlineDate") or ""
                for tok in medline.replace("-", " ").split():
                    if tok.isdigit() and len(tok) == 4:
                        year = tok
                        break
        if not year:
            return ""
        m = "01"
        if month:
            m = _MONTHS.get(month[:3].lower(), month.zfill(2) if month.isdigit() else "01")
        d = day.zfill(2) if (day and day.isdigit()) else "01"
        return f"{year}-{m}-{d}"

    @classmethod
    def _parse_article(cls, art: ET.Element) -> Article:
        pmid = art.findtext(".//PMID") or ""
        title = (art.findtext(".//ArticleTitle") or "").strip()
        # Abstracts can be split into multiple labelled sections.
        abstract = " ".join(
            (t.text or "").strip() for t in art.findall(".//Abstract/AbstractText")
        ).strip()
        return Article(
            pmid=pmid,
            title=title,
            abstract=abstract,
            pub_date=cls._parse_date(art),
            publication_types=[pt.text for pt in art.findall(".//PublicationType") if pt.text],
            mesh_descriptors=[m.findtext("DescriptorName") for m in art.findall(".//MeshHeading")
                              if m.findtext("DescriptorName")],
            chemicals=[c.findtext("NameOfSubstance") for c in art.findall(".//Chemical")
                       if c.findtext("NameOfSubstance")],
            journal=(art.findtext(".//Journal/Title") or "").strip(),
            authors=[
                f"{a.findtext('ForeName') or ''} {a.findtext('LastName') or ''}".strip()
                for a in art.findall(".//AuthorList/Author")
                if a.findtext("LastName")
            ][:6],
        )
