"""Command line entry point."""

from __future__ import annotations

import argparse
import json
import logging
import sys

import pandas as pd

from cnscoach.config import settings


def _wide() -> None:
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 50)
    pd.set_option("display.max_colwidth", 120)


def cmd_analyze(args: argparse.Namespace) -> int:
    from cnscoach.causal.engine import findings_to_frame
    from cnscoach.pipeline import run_analysis

    _wide()
    a = run_analysis(use_cache=not args.no_cache, with_negative_controls=not args.fast)

    print(f"\nPanel: {a.coverage['rows']:,} rows, {a.coverage['athletes']} athletes, "
          f"{a.coverage['date_min']} to {a.coverage['date_max']}")
    print(f"Median {a.coverage['days_per_athlete_median']:.0f} days per athlete\n")

    print(findings_to_frame(a.findings).to_string(index=False))

    print("\n" + "=" * 100)
    s = a.summary
    print(f"{s['n_hypotheses']} pre-registered hypotheses, {s['correction']}")
    print(f"  inference : {s['inference']}")
    print(f"  equivalence: {s['equivalence']}")
    for verdict, count in s["verdicts"].items():
        if count:
            print(f"  {verdict:<24} {count}")
    print(f"\n  statistically detectable : {s['n_statistically_detectable']}")
    print(f"  practically actionable   : {s['n_practically_actionable']}")
    print(f"  -> {s['pct_detectable_but_not_actionable']}% are detectable but not worth acting on")

    audit = a.audit
    if audit:
        print("\n" + "=" * 100)
        print("COMPOSITE SCORE AUDIT")
        print(f"  {audit['interpretation']}")

    if args.verbose:
        print("\n" + "=" * 100)
        for f in a.findings:
            print(f"\n* {f.plain_language}")
            if f.confounding_note:
                print(f"    caveat: {f.confounding_note}")
            if f.warnings:
                for w in f.warnings:
                    print(f"    warning: {w}")

    if args.json:
        payload = {
            "summary": s,
            "audit": audit,
            "findings": [f.to_dict() for f in a.findings],
        }
        print(json.dumps(payload, indent=2, default=str))
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    from cnscoach.causal.validation import validate_engine

    report = validate_engine(quick=args.quick, n_replications=args.replications)
    print(report.summary())
    return 0 if report.passed else 1


def cmd_score(args: argparse.Namespace) -> int:
    from cnscoach.cns import available, score_athlete_series, score_day
    from cnscoach.pipeline import run_analysis

    _wide()
    if args.list_models:
        for m in available():
            print(f"{m['name']:<16} v{m['version']}  {m['description']}")
        return 0

    a = run_analysis(use_cache=True)
    athlete = args.athlete or a.athletes()[0]

    if args.trend:
        series = score_athlete_series(a.features, athlete, model_name=args.model, last_n=args.trend)
        cols = [c for c in ("date", "cns_score", "band", "confidence", "calibrating",
                            "recovery_score", "day_strain", "hrv") if c in series]
        print(series[cols].to_string(index=False))
        return 0

    result = score_day(a.features, athlete, args.date, model_name=args.model)
    print(result.explain())
    return 0


def cmd_evidence(args: argparse.Namespace) -> int:
    from cnscoach.evidence import ATTRIBUTION, EvidenceStore

    store = EvidenceStore()
    if args.warm:
        print(f"Cached {store.warm()} articles in {settings.evidence_dir}")
        return 0

    for hit in store.search(args.query, limit=args.limit):
        a = hit.article
        print(f"\n[{hit.relevance:.2f}] {a.short_citation}")
        print(f"  {a.title}")
        print(f"  design: {a.evidence_tier}")
        if a.doi_url:
            print(f"  doi   : {a.doi_url}")
        if hit.curated_note:
            print(f"  supports    : {hit.curated_note['supports']}")
            print(f"  does NOT say: {hit.curated_note['does_not_support']}")
    print(f"\n{ATTRIBUTION}")
    return 0


def cmd_ask(args: argparse.Namespace) -> int:
    from cnscoach.coach import Coach
    from cnscoach.pipeline import run_analysis

    a = run_analysis(use_cache=True)
    coach = Coach(a.features, a.findings, strict=args.strict)
    if not coach.available:
        print(
            "No Anthropic API key set. Put CNSCOACH_ANTHROPIC_API_KEY in .env to enable "
            "the coach. The analysis, scoring and evidence commands all work without it.",
            file=sys.stderr,
        )
        return 2

    reply = coach.ask(args.question, athlete_id=args.athlete or a.athletes()[0])
    print(reply.render())
    return 0 if reply.is_grounded else 1


def cmd_calibrate(args: argparse.Namespace) -> int:
    from cnscoach.cns.calibrate import calibrate_weights
    from cnscoach.pipeline import run_analysis

    a = run_analysis(use_cache=True)
    result = calibrate_weights(
        a.features, outcome=args.outcome, model_name=args.model, max_athletes=args.athletes
    )
    print(result.summary())
    return 0


def cmd_clear_cache(args: argparse.Namespace) -> int:
    from cnscoach.pipeline import clear_cache

    print(f"Removed {clear_cache()} cached analysis file(s)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="cnscoach",
        description="Honest longitudinal inference over wearable data.",
    )
    parser.add_argument("-v", "--verbose-logging", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("analyze", help="Run the pre-registered hypothesis family")
    p.add_argument("--no-cache", action="store_true")
    p.add_argument("--fast", action="store_true", help="Skip permutation negative controls")
    p.add_argument("--verbose", action="store_true", help="Print full narratives")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_analyze)

    p = sub.add_parser("validate", help="Prove the engine recovers known effects")
    p.add_argument("--quick", action="store_true")
    p.add_argument("--replications", type=int, default=40)
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("score", help="Compute the CNS readiness score")
    p.add_argument("--athlete")
    p.add_argument("--date")
    p.add_argument("--model", default="v0_autonomic")
    p.add_argument("--trend", type=int, metavar="N", help="Show the last N days instead")
    p.add_argument("--list-models", action="store_true")
    p.set_defaults(func=cmd_score)

    p = sub.add_parser("evidence", help="Search the PubMed corpus")
    p.add_argument("query", nargs="?", default="")
    p.add_argument("--limit", type=int, default=5)
    p.add_argument("--warm", action="store_true", help="Pre-cache the curated corpus")
    p.set_defaults(func=cmd_evidence)

    p = sub.add_parser("ask", help="Ask the citation-locked coach")
    p.add_argument("question")
    p.add_argument("--athlete")
    p.add_argument("--strict", action="store_true", help="Refuse rather than annotate")
    p.set_defaults(func=cmd_ask)

    p = sub.add_parser("calibrate", help="Refit CNS weights against an outcome")
    p.add_argument("--outcome", default="recovery_score")
    p.add_argument("--model", default="v0_autonomic")
    p.add_argument("--athletes", type=int, default=60)
    p.set_defaults(func=cmd_calibrate)

    p = sub.add_parser("clear-cache", help="Delete cached analyses")
    p.set_defaults(func=cmd_clear_cache)

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose_logging else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
