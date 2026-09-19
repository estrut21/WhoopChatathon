"""PubMed retrieval via NCBI E-utilities, with an on-disk cache.

Scope discipline matters here. Literature explains *mechanism* — why an effect is
plausible, what direction to expect. It is never evidence about a particular athlete,
and the coach is forbidden from using a citation to support a numeric claim about the
user. A paper showing that HRV falls after high training load does not tell you what
your HRV did last Tuesday; only your data does.

That separation is enforced downstream in `cnscoach.coach.guardrails`. This module just
fetches and caches honestly, including recording when a fetch failed so a missing
citation is visibly missing rather than silently absent.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET

import httpx

from cnscoach.config import settings

log = logging.getLogger(__name__)

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


@dataclass
class Article:
    """A PubMed record, reduced to what a citation needs."""

    pmid: str
    title: str
    journal: str = ""
    year: str = ""
    authors: list[str] = field(default_factory=list)
    abstract: str = ""
    doi: str = ""
    pmc: str = ""
    publication_types: list[str] = field(default_factory=list)
    mesh_terms: list[str] = field(default_factory=list)
    retrieved_at: str = ""

    @property
    def short_citation(self) -> str:
        # Authors are stored "Lastname II", so the surname is the leading token.
        surname = self.authors[0].split()[0] if self.authors else "Anon"
        suffix = " et al." if len(self.authors) > 1 else ""
        return f"{surname}{suffix} ({self.year}), {self.journal}. PMID {self.pmid}"

    @property
    def url(self) -> str:
        return f"https://pubmed.ncbi.nlm.nih.gov/{self.pmid}/"

    @property
    def doi_url(self) -> str:
        return f"https://doi.org/{self.doi}" if self.doi else ""

    @property
    def evidence_tier(self) -> str:
        """A crude but honest study-design ranking, from the publication types.

        Shown next to every citation so a narrative review is not quoted as if it were
        a randomised trial.
        """
        types = {t.lower() for t in self.publication_types}
        if {"meta-analysis", "systematic review"} & types:
            return "systematic review / meta-analysis"
        if "randomized controlled trial" in types:
            return "randomised controlled trial"
        if "clinical trial" in types:
            return "clinical trial"
        if {"review", "narrative review"} & types:
            return "narrative review"
        if "observational study" in types:
            return "observational study"
        return "primary study (design unclassified)"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["short_citation"] = self.short_citation
        d["url"] = self.url
        d["evidence_tier"] = self.evidence_tier
        return d


class PubMedClient:
    """Cached E-utilities client.

    NCBI asks for a tool name and contact email, and rate-limits to ~3 requests/second
    without an API key. Both are honoured.
    """

    def __init__(
        self,
        cache_dir: Path | None = None,
        *,
        api_key: str | None = None,
        email: str | None = None,
        ttl_days: int | None = None,
    ) -> None:
        self.cache_dir = Path(cache_dir or settings.evidence_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.api_key = api_key or settings.ncbi_api_key
        self.email = email or settings.ncbi_email
        self.ttl = timedelta(days=ttl_days or settings.pubmed_cache_ttl_days)
        self._min_interval = 0.11 if self.api_key else 0.34
        self._last_call = 0.0

    # -- plumbing ----------------------------------------------------------------

    def _params(self, **kw) -> dict:
        p = {"tool": settings.ncbi_tool, **kw}
        if self.api_key:
            p["api_key"] = self.api_key
        if self.email:
            p["email"] = self.email
        return p

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_call
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_call = time.monotonic()

    def _cache_path(self, pmid: str) -> Path:
        return self.cache_dir / f"pmid_{pmid}.json"

    def _read_cache(self, pmid: str) -> Article | None:
        path = self._cache_path(pmid)
        if not path.exists():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            fetched = datetime.fromisoformat(raw.get("retrieved_at", "1970-01-01T00:00:00+00:00"))
            if datetime.now(UTC) - fetched > self.ttl:
                return None
            known = {f for f in Article.__dataclass_fields__}
            return Article(**{k: v for k, v in raw.items() if k in known})
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            log.debug("Bad cache entry for %s: %s", pmid, exc)
            return None

    def _write_cache(self, article: Article) -> None:
        self._cache_path(article.pmid).write_text(
            json.dumps(article.to_dict(), indent=2), encoding="utf-8"
        )

    # -- public API ---------------------------------------------------------------

    def fetch(self, pmids: list[str], *, use_cache: bool = True) -> dict[str, Article]:
        """Fetch records by PMID, preferring the cache."""
        out: dict[str, Article] = {}
        missing: list[str] = []

        for pmid in pmids:
            cached = self._read_cache(pmid) if use_cache else None
            if cached:
                out[pmid] = cached
            else:
                missing.append(pmid)

        if not missing:
            return out

        try:
            self._throttle()
            with httpx.Client(timeout=30.0) as client:
                r = client.get(
                    f"{EUTILS}/efetch.fcgi",
                    params=self._params(db="pubmed", id=",".join(missing), retmode="xml"),
                )
                r.raise_for_status()
            for article in _parse_efetch(r.text):
                self._write_cache(article)
                out[article.pmid] = article
        except (httpx.HTTPError, ET.ParseError) as exc:
            log.warning("PubMed fetch failed for %s: %s", missing, exc)

        return out

    def search(self, query: str, *, max_results: int = 20, sort: str = "relevance") -> list[str]:
        """Return PMIDs matching a query. Accepts full PubMed field syntax."""
        try:
            self._throttle()
            with httpx.Client(timeout=30.0) as client:
                r = client.get(
                    f"{EUTILS}/esearch.fcgi",
                    params=self._params(
                        db="pubmed",
                        term=query,
                        retmax=max_results,
                        retmode="json",
                        sort=sort,
                    ),
                )
                r.raise_for_status()
                return r.json().get("esearchresult", {}).get("idlist", [])
        except (httpx.HTTPError, json.JSONDecodeError, KeyError) as exc:
            log.warning("PubMed search failed for %r: %s", query, exc)
            return []

    def search_and_fetch(self, query: str, *, max_results: int = 10) -> list[Article]:
        pmids = self.search(query, max_results=max_results)
        found = self.fetch(pmids)
        return [found[p] for p in pmids if p in found]


def _text(node: ET.Element | None, default: str = "") -> str:
    if node is None:
        return default
    return "".join(node.itertext()).strip() or default


def _parse_efetch(xml: str) -> list[Article]:
    """Parse an efetch PubmedArticleSet into Article records."""
    root = ET.fromstring(xml)
    now = datetime.now(UTC).isoformat()
    articles: list[Article] = []

    for art in root.findall(".//PubmedArticle"):
        medline = art.find("MedlineCitation")
        if medline is None:
            continue
        pmid = _text(medline.find("PMID"))
        if not pmid:
            continue
        a = medline.find("Article")
        if a is None:
            continue

        journal = a.find("Journal")
        year = ""
        if journal is not None:
            year = _text(journal.find(".//PubDate/Year")) or _text(
                journal.find(".//PubDate/MedlineDate")
            )[:4]

        authors = []
        for au in a.findall(".//AuthorList/Author"):
            last, initials = _text(au.find("LastName")), _text(au.find("Initials"))
            if last:
                authors.append(f"{last} {initials}".strip())

        # Structured abstracts arrive as several labelled sections.
        parts = []
        for chunk in a.findall(".//Abstract/AbstractText"):
            label = chunk.get("Label")
            body = _text(chunk)
            parts.append(f"{label}: {body}" if label else body)

        # Scope to PubmedData: a `.//ArticleIdList` search also matches the identifier
        # lists inside <ReferenceList>, which would silently attribute a cited paper's
        # DOI to this one. Take the first of each type, not the last.
        ids: dict[str, str] = {}
        for el in art.findall("./PubmedData/ArticleIdList/ArticleId"):
            id_type = el.get("IdType") or ""
            if id_type and id_type not in ids:
                ids[id_type] = _text(el)

        articles.append(
            Article(
                pmid=pmid,
                title=_text(a.find("ArticleTitle")),
                journal=_text(journal.find("ISOAbbreviation")) if journal is not None else "",
                year=year,
                authors=authors,
                abstract=" ".join(parts),
                doi=ids.get("doi", ""),
                pmc=ids.get("pmc", ""),
                publication_types=[_text(t) for t in a.findall(".//PublicationTypeList/PublicationType")],
                mesh_terms=[
                    _text(m.find("DescriptorName"))
                    for m in medline.findall(".//MeshHeadingList/MeshHeading")
                ],
                retrieved_at=now,
            )
        )
    return articles
