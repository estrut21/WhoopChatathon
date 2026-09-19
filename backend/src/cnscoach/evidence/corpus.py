"""The curated evidence corpus and retrieval over it.

Every PMID here was checked by hand against the claim it is attached to. That matters
more than corpus size: a large auto-assembled bibliography where half the papers do not
say what the citation implies is worse than a small one that does, because it launders
unfounded claims through the appearance of rigour.

Retrieval is deliberately keyword-based rather than embedding-based. With a corpus this
size an embedding index adds a dependency and a failure mode without adding recall, and
keyword matching is auditable — you can see exactly why a paper was returned.
"""

from __future__ import annotations

from dataclasses import dataclass

from cnscoach.causal.hypotheses import HYPOTHESES
from cnscoach.evidence.pubmed import Article, PubMedClient

#: PMIDs verified as relevant to this project's claims, with the scope of what each one
#: does and does not support. The `supports` text is what the coach may paraphrase; it
#: is intentionally narrow.
CURATED: dict[str, dict[str, str]] = {
    "37754967": {
        "topic": "training load -> autonomic recovery",
        "supports": (
            "In collegiate American football players, higher acute and cumulative "
            "exercise cardiac load was associated with slower maximum running speed, and "
            "HRV metrics were positively associated with running speed."
        ),
        "does_not_support": (
            "Not a randomised trial; cannot establish that reducing load causes faster "
            "recovery. Single sport, young male-dominated cohort."
        ),
    },
    "31642195": {
        "topic": "dose-dependent autonomic adaptation",
        "supports": (
            "In elite weightlifters, HRV indices tracked training load dose-dependently "
            "on an individual basis, and the direction of adaptation was opposite to that "
            "reported for endurance athletes."
        ),
        "does_not_support": (
            "n=9. The sport-specificity finding is a caution against assuming one HRV "
            "response curve fits all training modalities."
        ),
    },
    "33202732": {
        "topic": "HRV across a training cycle",
        "supports": (
            "Cardiac parasympathetic modulation declined across a 15-week season in youth "
            "female rowers, though no significant relationship with training load was found."
        ),
        "does_not_support": (
            "n=7. The authors explicitly note non-training stressors may drive the decline. "
            "This is evidence that HRV drifts over a season, not that load explains it."
        ),
    },
    "35344471": {
        "topic": "training monotony, strain and overreaching",
        "supports": (
            "In women's water polo, training load was monitored with session-RPE, monotony "
            "and strain; five of 20 athletes were classified as overreaching."
        ),
        "does_not_support": (
            "The authors found physiological markers including lnRMSSD showed LITTLE "
            "sensitivity to changes in training load and performance. Do not cite this as "
            "evidence that HRV tracks load well - it reports the opposite."
        ),
    },
    "30300066": {
        "topic": "lnRMSSD interpretation caveats",
        "supports": (
            "In elite synchronised swimmers, isolated HRV assessment could give a "
            "misleading picture of autonomic status because the diving response confounds "
            "it."
        ),
        "does_not_support": (
            "Sport-specific confounding. The general lesson is that a single HRV reading "
            "is not self-interpreting, not that HRV is useless."
        ),
    },
    "35409591": {
        "topic": "central vs peripheral fatigue",
        "supports": (
            "Narrative review of central and peripheral fatigue mechanisms, noting that "
            "sleep deprivation and psychological stress alter neural activation patterns."
        ),
        "does_not_support": (
            "Narrative review, not systematic. Provides mechanism and vocabulary, not "
            "effect sizes."
        ),
    },
    "14965189": {
        "topic": "central fatigue after prolonged exercise",
        "supports": (
            "Review of neuromuscular alterations after prolonged running, cycling and "
            "skiing; central fatigue contributes to strength loss, and its magnitude is "
            "task-dependent."
        ),
        "does_not_support": (
            "Concerns acute post-exercise neuromuscular function measured in a lab, not "
            "next-day wearable readiness."
        ),
    },
}


@dataclass
class EvidenceHit:
    article: Article
    relevance: float
    matched_terms: list[str]
    curated_note: dict[str, str] | None = None

    def to_dict(self) -> dict:
        return {
            **self.article.to_dict(),
            "relevance": round(self.relevance, 3),
            "matched_terms": self.matched_terms,
            "supports": (self.curated_note or {}).get("supports", ""),
            "does_not_support": (self.curated_note or {}).get("does_not_support", ""),
        }


class EvidenceStore:
    """Keyword retrieval over the curated corpus, with live PubMed as a fallback."""

    def __init__(self, client: PubMedClient | None = None) -> None:
        self.client = client or PubMedClient()
        self._articles: dict[str, Article] = {}

    def warm(self, pmids: list[str] | None = None) -> int:
        """Populate the cache. Returns how many records are available."""
        wanted = pmids or sorted(set(CURATED) | set(_hypothesis_pmids()))
        self._articles.update(self.client.fetch(wanted))
        return len(self._articles)

    def _ensure(self) -> None:
        if not self._articles:
            self.warm()

    def get(self, pmid: str) -> Article | None:
        self._ensure()
        if pmid not in self._articles:
            self._articles.update(self.client.fetch([pmid]))
        return self._articles.get(pmid)

    def for_hypothesis(self, hypothesis_id: str) -> list[EvidenceHit]:
        """The papers pre-registered against a specific hypothesis."""
        self._ensure()
        h = next((x for x in HYPOTHESES if x.id == hypothesis_id), None)
        if h is None:
            return []
        hits = []
        for pmid in h.pmids:
            art = self.get(pmid)
            if art:
                hits.append(
                    EvidenceHit(art, relevance=1.0, matched_terms=["pre-registered"],
                                curated_note=CURATED.get(pmid))
                )
        return hits

    def search(self, query: str, *, limit: int = 5, live_fallback: bool = True) -> list[EvidenceHit]:
        """Score the local corpus by term overlap; fall back to PubMed if it is thin."""
        self._ensure()
        terms = [t for t in _tokenise(query) if len(t) > 3]
        if not terms:
            return []

        hits: list[EvidenceHit] = []
        for pmid, art in self._articles.items():
            haystack = _tokenise(
                " ".join([art.title, art.abstract, " ".join(art.mesh_terms),
                          CURATED.get(pmid, {}).get("topic", "")])
            )
            matched = [t for t in terms if t in haystack]
            if matched:
                hits.append(
                    EvidenceHit(
                        article=art,
                        relevance=len(matched) / len(terms),
                        matched_terms=matched,
                        curated_note=CURATED.get(pmid),
                    )
                )

        hits.sort(key=lambda h: -h.relevance)
        if len(hits) < limit and live_fallback:
            for art in self.client.search_and_fetch(query, max_results=limit):
                if art.pmid not in {h.article.pmid for h in hits}:
                    self._articles[art.pmid] = art
                    hits.append(
                        EvidenceHit(art, relevance=0.5, matched_terms=["live PubMed search"],
                                    curated_note=CURATED.get(art.pmid))
                    )
        return hits[:limit]


def _tokenise(text: str) -> set[str]:
    return {w.strip(".,;:()[]'\"").lower() for w in text.split()}


def _hypothesis_pmids() -> list[str]:
    out: list[str] = []
    for h in HYPOTHESES:
        out.extend(p for p in h.pmids if p not in out)
    return out


ATTRIBUTION = (
    "Literature retrieved from PubMed (NCBI). Citations include DOI links to the "
    "original articles; PubMed and the original authors retain all credit."
)
