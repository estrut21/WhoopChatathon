"""Tools the coach may call, and their executor.

The tool surface *is* the coach's epistemic boundary. It can answer exactly what these
functions return and nothing else, which is why there is no free-text "analyse" tool:
every question has to route through a pre-registered hypothesis or a literal data
lookup, and anything outside that comes back as "not available" rather than as prose.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd

from cnscoach.causal.engine import Finding, findings_to_frame, score_audit
from cnscoach.causal.hypotheses import HYPOTHESES
from cnscoach.cns import circularity_report, score_athlete_series, score_day
from cnscoach.coach.guardrails import FactLedger
from cnscoach.data.loader import panel_summary
from cnscoach.data.schema import ATHLETE_ID, DATE
from cnscoach.evidence import EvidenceStore

log = logging.getLogger(__name__)


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "list_findings",
        "description": (
            "List every pre-registered hypothesis that has been tested, with its verdict, "
            "effect size, confidence interval and corrected p-value. Start here for any "
            "question about what does or does not affect this athlete. Returns nulls and "
            "inconclusive results too — those are findings, not gaps."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "verdict": {
                    "type": "string",
                    "enum": [
                        "supported",
                        "detectable_but_trivial",
                        "negligible",
                        "inconclusive",
                        "direction_reversed",
                    ],
                    "description": "Optional filter by verdict.",
                },
                "outcome": {
                    "type": "string",
                    "description": "Optional filter, e.g. 'hrv' or 'recovery_score'.",
                },
            },
        },
    },
    {
        "name": "get_finding",
        "description": (
            "Full detail for one hypothesis: coefficient, CI, corrected p-value, "
            "equivalence test, minimum detectable effect, dose-response curve, negative "
            "control, confounding caveat, and the exact sentence that may be quoted."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "hypothesis_id": {
                    "type": "string",
                    "description": "e.g. 'A1_strain_to_hrv'. Get valid ids from list_findings.",
                }
            },
            "required": ["hypothesis_id"],
        },
    },
    {
        "name": "query_athlete_data",
        "description": (
            "Retrieve this athlete's actual daily rows. Use when asked about specific "
            "days or recent trends. Returns real measured values, never interpolated."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "athlete_id": {"type": "string"},
                "columns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Columns to return, e.g. ['hrv','sleep_hours','day_strain'].",
                },
                "last_n_days": {"type": "integer", "description": "Default 14, max 90."},
                "start_date": {"type": "string", "description": "YYYY-MM-DD, optional."},
                "end_date": {"type": "string", "description": "YYYY-MM-DD, optional."},
            },
            "required": ["athlete_id", "columns"],
        },
    },
    {
        "name": "get_cns_score",
        "description": (
            "Compute the transparent CNS readiness score for one athlete-day, returning "
            "every component, its weight and its contribution. Also reports whether the "
            "baseline is still calibrating."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "athlete_id": {"type": "string"},
                "date": {"type": "string", "description": "YYYY-MM-DD. Omit for the latest day."},
                "model": {"type": "string", "description": "Default 'v0_autonomic'."},
            },
            "required": ["athlete_id"],
        },
    },
    {
        "name": "get_score_trend",
        "description": "CNS score over recent days for one athlete, alongside WHOOP's recovery score.",
        "input_schema": {
            "type": "object",
            "properties": {
                "athlete_id": {"type": "string"},
                "last_n_days": {"type": "integer", "description": "Default 30, max 120."},
            },
            "required": ["athlete_id"],
        },
    },
    {
        "name": "search_literature",
        "description": (
            "Search the curated PubMed corpus for mechanism. Returns citations with PMIDs, "
            "DOIs, study design and — importantly — what each paper does NOT support. "
            "Literature never licenses a numeric claim about this athlete."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "description": "Default 3, max 8."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_data_coverage",
        "description": (
            "What data actually exists: row counts, date range, athlete count, available "
            "columns. Call this before saying something is unavailable, and to check "
            "whether a column exists at all."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "check_score_circularity",
        "description": (
            "Check whether an exposure is itself an input to the CNS score before "
            "comparing the two. Prevents presenting a relationship that holds by "
            "construction as if it were evidence."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "athlete_id": {"type": "string"},
                "exposure": {"type": "string", "description": "e.g. 'day_strain_lag1'."},
            },
            "required": ["athlete_id", "exposure"],
        },
    },
]


class ToolExecutor:
    """Runs tool calls and records every number they return into the fact ledger."""

    MAX_ROWS = 90

    def __init__(
        self,
        features: pd.DataFrame,
        findings: list[Finding],
        ledger: FactLedger,
        evidence: EvidenceStore | None = None,
    ) -> None:
        self.features = features
        self.findings = {f.hypothesis_id: f for f in findings}
        self.ledger = ledger
        self.evidence = evidence or EvidenceStore()

    # -- dispatch -----------------------------------------------------------------

    def run(self, name: str, args: dict) -> dict:
        handler: Callable[..., dict] | None = getattr(self, f"_t_{name}", None)
        if handler is None:
            return {"error": f"Unknown tool '{name}'"}
        try:
            result = handler(**args)
        except TypeError as exc:
            return {"error": f"Bad arguments for {name}: {exc}"}
        except (KeyError, ValueError) as exc:
            return {"error": str(exc), "available": True}
        except Exception as exc:  # pragma: no cover - surfaced rather than swallowed
            log.exception("Tool %s failed", name)
            return {"error": f"{type(exc).__name__}: {exc}"}

        self.ledger.add_mapping(result, source=f"{name}({_brief(args)})")
        return result

    # -- tools --------------------------------------------------------------------

    def _t_list_findings(self, verdict: str | None = None, outcome: str | None = None) -> dict:
        rows = []
        for f in self.findings.values():
            if verdict and f.verdict.value != verdict:
                continue
            if outcome and f.outcome != outcome:
                continue
            rows.append(
                {
                    "hypothesis_id": f.hypothesis_id,
                    "question": f.question,
                    "verdict": f.verdict.value,
                    "outcome": f.outcome,
                    "exposure": f.exposure,
                    "coef": round(f.coef, 4),
                    "ci_low": round(f.ci_low, 4),
                    "ci_high": round(f.ci_high, 4),
                    "p_holm": float(f"{f.p_adjusted:.3g}"),
                    "n_obs": f.n_obs,
                    "n_athletes": f.n_athletes,
                }
            )
        return {
            "n_findings": len(rows),
            "findings": rows,
            "note": (
                "Verdicts are not interchangeable. 'negligible' means ruled out as a "
                "practical influence; 'inconclusive' means the data cannot tell."
            ),
        }

    def _t_get_finding(self, hypothesis_id: str) -> dict:
        f = self.findings.get(hypothesis_id)
        if f is None:
            return {
                "error": f"No finding '{hypothesis_id}'",
                "valid_ids": sorted(self.findings),
            }
        d = f.to_dict()
        d["quotable_claim"] = f.quotable_claim
        d["caution"] = (
            "Observational. Use associational language. Quote `quotable_claim` verbatim "
            "if you want a safe summary sentence."
        )
        return d

    def _t_query_athlete_data(
        self,
        athlete_id: str,
        columns: list[str],
        last_n_days: int = 14,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict:
        sub = self.features[self.features[ATHLETE_ID] == athlete_id]
        if sub.empty:
            return {
                "error": f"No athlete '{athlete_id}'",
                "available_athletes_sample": self.features[ATHLETE_ID].unique()[:5].tolist(),
            }

        missing = [c for c in columns if c not in self.features.columns]
        keep = [c for c in columns if c in self.features.columns]
        if not keep:
            return {
                "error": "None of the requested columns exist",
                "requested": columns,
                "available_columns": sorted(self.features.columns),
            }

        sub = sub.sort_values(DATE)
        if start_date:
            sub = sub[sub[DATE] >= pd.Timestamp(start_date)]
        if end_date:
            sub = sub[sub[DATE] <= pd.Timestamp(end_date)]
        if not start_date and not end_date:
            sub = sub.tail(min(int(last_n_days), self.MAX_ROWS))

        out = sub[[DATE, *keep]].copy()
        out[DATE] = out[DATE].dt.strftime("%Y-%m-%d")
        records = json.loads(out.replace({np.nan: None}).to_json(orient="records"))

        return {
            "athlete_id": athlete_id,
            "n_rows": len(records),
            "columns_returned": keep,
            "columns_not_found": missing,
            "rows": records,
            "note": "Measured values only. Missing entries are null, never imputed.",
        }

    def _t_get_cns_score(
        self, athlete_id: str, date: str | None = None, model: str = "v0_autonomic"
    ) -> dict:
        sub = self.features[self.features[ATHLETE_ID] == athlete_id]
        if sub.empty:
            return {"error": f"No athlete '{athlete_id}'"}
        result = score_day(self.features, athlete_id, date, model_name=model)
        d = result.to_dict()
        d["explanation"] = result.explain()
        return d

    def _t_get_score_trend(self, athlete_id: str, last_n_days: int = 30) -> dict:
        n = min(int(last_n_days), 120)
        series = score_athlete_series(self.features, athlete_id, last_n=n)
        cols = [c for c in (DATE, "cns_score", "band", "confidence", "calibrating",
                            "recovery_score", "day_strain", "hrv") if c in series]
        out = series[cols].copy()
        out[DATE] = out[DATE].dt.strftime("%Y-%m-%d")
        return {
            "athlete_id": athlete_id,
            "n_days": len(out),
            "rows": json.loads(out.replace({np.nan: None}).to_json(orient="records")),
            "note": (
                "cns_score and recovery_score are different scales and are not directly "
                "comparable in level. Compare their movement, not their values."
            ),
        }

    def _t_search_literature(self, query: str, limit: int = 3) -> dict:
        hits = self.evidence.search(query, limit=min(int(limit), 8))
        return {
            "query": query,
            "n_results": len(hits),
            "results": [
                {
                    "pmid": h.article.pmid,
                    "citation": h.article.short_citation,
                    "title": h.article.title,
                    "doi_url": h.article.doi_url,
                    "url": h.article.url,
                    "study_design": h.article.evidence_tier,
                    "supports": (h.curated_note or {}).get("supports", ""),
                    "does_not_support": (h.curated_note or {}).get("does_not_support", ""),
                }
                for h in hits
            ],
            "attribution": (
                "Retrieved from PubMed (NCBI). Cite the PMID and DOI when referencing."
            ),
            "scope": (
                "Mechanism only. These papers say nothing about this particular athlete "
                "and must not be used to support a numeric claim about them."
            ),
        }

    def _t_get_data_coverage(self) -> dict:
        s = panel_summary(self.features)
        s["score_audit"] = score_audit(list(self.findings.values()))
        s["n_hypotheses_tested"] = len(self.findings)
        s["note"] = (
            "Columns absent from this list do not exist. Journal tags (alcohol, caffeine, "
            "stress, mood) are NOT in this dataset; questions about them cannot be answered."
        )
        return s

    def _t_check_score_circularity(self, athlete_id: str, exposure: str) -> dict:
        sub = self.features[self.features[ATHLETE_ID] == athlete_id]
        if sub.empty:
            return {"error": f"No athlete '{athlete_id}'"}
        return circularity_report(score_day(self.features, athlete_id), exposure)


def _brief(args: dict) -> str:
    return ", ".join(f"{k}={v!r}" for k, v in list(args.items())[:3])


def findings_table(findings: list[Finding]) -> str:
    """A compact rendering of the whole family, for the system prompt preamble."""
    return findings_to_frame(findings).to_string(index=False)


__all__ = ["HYPOTHESES", "TOOL_SCHEMAS", "ToolExecutor", "findings_table"]
