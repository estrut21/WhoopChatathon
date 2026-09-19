"""FastAPI surface.

The analysis is computed once at startup and held in memory: the family takes about
eight seconds over 100,000 rows, which is fine as a cold start and unacceptable per
request.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from cnscoach.cns import available as available_models
from cnscoach.cns import circularity_report, score_athlete_series, score_day
from cnscoach.config import settings
from cnscoach.evidence import ATTRIBUTION, EvidenceStore
from cnscoach.pipeline import Analysis, run_analysis

log = logging.getLogger(__name__)

STATE: dict[str, Any] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Running analysis at startup...")
    STATE["analysis"] = run_analysis(use_cache=True)
    STATE["evidence"] = EvidenceStore()
    log.info("Ready: %d findings", len(STATE["analysis"].findings))
    yield
    STATE.clear()


app = FastAPI(
    title="cns-coach",
    version="0.1.0",
    description=(
        "Honest longitudinal inference over wearable data, a transparent CNS readiness "
        "score, and a citation-locked coach."
    ),
    lifespan=lifespan,
)


def analysis() -> Analysis:
    a = STATE.get("analysis")
    if a is None:  # pragma: no cover - only before startup completes
        raise HTTPException(503, "Analysis not ready")
    return a


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3)
    athlete_id: str | None = None
    strict: bool = False


@app.get("/health")
def health() -> dict:
    a = STATE.get("analysis")
    return {
        "status": "ok" if a else "starting",
        "findings": len(a.findings) if a else 0,
        "model": settings.model,
        "coach_enabled": bool(settings.anthropic_api_key),
    }


@app.get("/coverage")
def coverage() -> dict:
    """What data exists. Call before assuming a column is available."""
    a = analysis()
    return {**a.coverage, "n_hypotheses": len(a.findings)}


@app.get("/findings")
def findings(
    verdict: str | None = Query(None),
    outcome: str | None = Query(None),
) -> dict:
    a = analysis()
    items = [
        f.to_dict()
        for f in a.findings
        if (verdict is None or f.verdict.value == verdict)
        and (outcome is None or f.outcome == outcome)
    ]
    return {"n": len(items), "summary": a.summary, "findings": items}


@app.get("/findings/{hypothesis_id}")
def finding(hypothesis_id: str) -> dict:
    a = analysis()
    try:
        return a.finding(hypothesis_id).to_dict()
    except KeyError:
        raise HTTPException(
            404, f"No finding '{hypothesis_id}'. Valid: {[f.hypothesis_id for f in a.findings]}"
        ) from None


@app.get("/score-audit")
def score_audit_endpoint() -> dict:
    """Does the proprietary composite retain the load signal its own inputs carry?"""
    audit = analysis().audit
    if audit is None:
        raise HTTPException(404, "Score audit unavailable (required hypotheses missing)")
    return audit


@app.get("/athletes")
def athletes(limit: int = Query(50, le=500)) -> dict:
    a = analysis()
    ids = a.athletes()
    return {"n_total": len(ids), "athlete_ids": ids[:limit]}


@app.get("/athletes/{athlete_id}/cns")
def cns_score(athlete_id: str, date: str | None = None, model: str = "v0_autonomic") -> dict:
    a = analysis()
    sub = a.features[a.features.athlete_id == athlete_id]
    if sub.empty:
        raise HTTPException(404, f"No athlete '{athlete_id}'")
    try:
        result = score_day(a.features, athlete_id, date, model_name=model)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from None
    return {**result.to_dict(), "explanation": result.explain()}


@app.get("/athletes/{athlete_id}/cns/trend")
def cns_trend(athlete_id: str, days: int = Query(30, le=200), model: str = "v0_autonomic") -> dict:
    a = analysis()
    try:
        series = score_athlete_series(a.features, athlete_id, model_name=model, last_n=days)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from None
    out = series.copy()
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    return {"athlete_id": athlete_id, "rows": out.where(out.notna(), None).to_dict("records")}


@app.get("/athletes/{athlete_id}/circularity")
def circularity(athlete_id: str, exposure: str) -> dict:
    """Is `exposure` an ingredient of the score you are about to test it against?"""
    a = analysis()
    sub = a.features[a.features.athlete_id == athlete_id]
    if sub.empty:
        raise HTTPException(404, f"No athlete '{athlete_id}'")
    return circularity_report(score_day(a.features, athlete_id), exposure)


@app.get("/models")
def models() -> dict:
    return {"models": available_models()}


@app.get("/evidence")
def evidence(query: str, limit: int = Query(5, le=20)) -> dict:
    store: EvidenceStore = STATE["evidence"]
    hits = store.search(query, limit=limit)
    return {
        "query": query,
        "attribution": ATTRIBUTION,
        "results": [h.to_dict() for h in hits],
    }


@app.post("/ask")
def ask(req: AskRequest) -> dict:
    """Ask the coach. Every number in the reply is verified against retrieved data."""
    from cnscoach.coach import Coach

    a = analysis()
    coach = Coach(a.features, a.findings, strict=req.strict, evidence=STATE["evidence"])
    if not coach.available:
        raise HTTPException(
            503,
            "Coach disabled: no Anthropic API key configured. Set CNSCOACH_ANTHROPIC_API_KEY.",
        )

    reply = coach.ask(req.question, athlete_id=req.athlete_id)
    return {
        "answer": reply.text,
        "grounded": reply.is_grounded,
        "blocked": reply.blocked,
        "grounding": {
            "summary": reply.grounding.summary(),
            "n_verified": len(reply.grounding.verified),
            "n_violations": len(reply.grounding.violations),
            "collision_rate": reply.grounding.collision_rate,
            "ledger_size": reply.grounding.ledger_size,
            "violations": [
                {"value": v.value, "context": v.context, "reason": v.reason}
                for v in reply.grounding.violations
            ],
        },
        "tool_calls": reply.tool_calls,
        "citations": reply.citations,
    }
