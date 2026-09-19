"""The causal analysis engine.

Runs the pre-registered family, corrects for multiplicity, and classifies every result
into one of four verdicts — including the two that most analytics products never emit:
"bounded and negligible" and "we cannot tell".

The output of `run_family()` is the *only* thing the coach is permitted to make
quantitative claims from. Each `Finding` carries a `quotable_claim` string; the
guardrail layer in `cnscoach.coach.guardrails` rejects any generated number that does
not trace back to one.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from enum import Enum

import numpy as np
import pandas as pd

from cnscoach.causal import estimators as est
from cnscoach.causal.hypotheses import HYPOTHESES, Hypothesis
from cnscoach.config import settings
from cnscoach.data.schema import ATHLETE_ID, COLUMN_DOCS

log = logging.getLogger(__name__)


class Verdict(str, Enum):
    """What the statistics actually licence us to say.

    Statistical significance and practical importance are orthogonal, and at n=100,000
    they come apart constantly. Collapsing them into "significant / not significant" is
    how a dataset like this produces confident nonsense. Five verdicts, because the
    cross of (detectably nonzero?) x (bounded below the actionable threshold?) has four
    cells and one of them needs splitting by sign.
    """

    SUPPORTED = "supported"
    """Detectably nonzero after family-wise correction, and large enough to act on."""

    DETECTABLE_BUT_TRIVIAL = "detectable_but_trivial"
    """Real — the correction did not kill it — but bounded below the threshold of
    practical relevance. The most common honest verdict in large wearable panels, and
    the one no consumer app will show you."""

    NEGLIGIBLE = "negligible"
    """Bounded inside the region of practical equivalence *and* indistinguishable from
    zero. An affirmative 'no, this doesn't matter' — not a failure to find something."""

    INCONCLUSIVE = "inconclusive"
    """Cannot reject zero, and cannot bound the effect below the practical threshold
    either. The honest answer is that this dataset can't settle it."""

    DIRECTION_REVERSED = "direction_reversed"
    """Detectably nonzero and practically relevant, but with the opposite sign to the
    pre-registered expectation. Reported loudly rather than quietly dropped."""


VERDICT_PHRASING = {
    Verdict.SUPPORTED: "Supported, and big enough to matter",
    Verdict.DETECTABLE_BUT_TRIVIAL: "Real but too small to act on",
    Verdict.NEGLIGIBLE: "No meaningful effect (and we can say that positively)",
    Verdict.INCONCLUSIVE: "Not enough signal to tell",
    Verdict.DIRECTION_REVERSED: "Real, but opposite to what was expected",
}

UNITS = {
    "hrv": "ms",
    "resting_heart_rate": "bpm",
    "recovery_score": "pts",
    "respiratory_rate": "breaths/min",
    "sleep_hours": "h",
    "ln_hrv": "log-ms",
}


@dataclass
class Finding:
    """One hypothesis, answered, with every caveat attached."""

    hypothesis_id: str
    family: str
    question: str
    verdict: Verdict

    outcome: str
    exposure: str
    covariates: list[str]

    coef: float
    se: float
    ci_low: float
    ci_high: float
    p_value: float
    p_adjusted: float
    n_obs: int
    n_athletes: int
    r2_within: float

    effect_per_exposure_sd: float
    pct_of_outcome_sd: float
    mde_80: float
    rope: float
    rope_sd_frac: float
    equivalence_p: float

    plain_language: str
    quotable_claim: str
    confounding_note: str
    pmids: list[str]

    #: Within-athlete 10th-to-90th-percentile range of the exposure. Used to restate
    #: per-unit coefficients over a swing an athlete would actually experience — "per
    #: strain point" is not a quantity anyone has intuition for.
    realistic_swing: float = float("nan")

    warnings: list[str] = field(default_factory=list)

    negative_control: dict | None = None
    dose_response: list[dict] | None = None
    dose_monotonic: bool | None = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["verdict"] = self.verdict.value
        return d


def _fmt_effect(coef: float, outcome: str, per: str) -> str:
    unit = UNITS.get(outcome, "units")
    direction = "a fall of" if coef < 0 else "a rise of"
    return f"{direction} {abs(coef):.3g} {unit} per {per}"


def _fmt_ci(lo: float, hi: float, outcome: str) -> str:
    unit = UNITS.get(outcome, "units")
    return f"95% CI {lo:+.3g} to {hi:+.3g} {unit}"


def _exposure_label(exposure: str) -> str:
    """A readable noun phrase for the exposure's unit."""
    pretty = {
        "day_strain_lag1": "strain point yesterday",
        "day_strain_lag2": "strain point two days ago",
        "sleep_hours_lag1": "hour of sleep",
        "high_intensity_min_lag1": "minute in zones 4-5",
        "wake_ups_lag1": "awakening",
        "acwr": "unit of acute:chronic ratio",
        "sleep_debt_7d": "hour of 7-day sleep debt",
        "sleep_irregularity": "hour of sleep-duration SD",
        "consecutive_training_days": "consecutive training day",
        "monotony": "unit of monotony",
        "respiratory_rate_z": "SD of respiratory rate",
        "skin_temp_deviation": "°C of skin-temp deviation",
        "double_hit_prev": "short-sleep-plus-hard-day night",
        "hrv": "ms of HRV",
    }
    return pretty.get(exposure, f"unit of {exposure}")


def run_hypothesis(
    df: pd.DataFrame,
    h: Hypothesis,
    *,
    with_negative_control: bool = False,
    with_dose_response: bool = True,
    n_permutations: int = 200,
) -> Finding | None:
    """Fit one hypothesis. Returns None if the panel can't support it at all."""
    available = set(df.columns)
    covariates = tuple(c for c in h.covariates if c in available)
    skipped = [c for c in h.covariates if c not in available]

    if h.outcome not in available or h.exposure not in available:
        log.warning("Skipping %s: outcome or exposure not in panel", h.id)
        return None

    try:
        fit = est.within_athlete_fe(df, h.outcome, [h.exposure], covariates)
    except (ValueError, KeyError) as exc:
        log.warning("Skipping %s: %s", h.id, exc)
        return None

    e = fit.get(h.exposure)
    warnings = list(fit.warnings)
    if skipped:
        warnings.append(f"covariates unavailable and omitted: {skipped}")

    # ROPE in coefficient units: `rope_sd_frac` of the outcome's within-athlete SD,
    # expressed per one SD of exposure, then converted back to per-unit-of-exposure.
    rope = float(h.rope_sd_frac * e.outcome_sd / e.exposure_sd) if e.exposure_sd else np.nan
    e.rope = rope
    equivalence_p = est.tost_equivalence(e, rope) if rope and np.isfinite(rope) else np.nan
    e.equivalence_p = equivalence_p

    # A realistic exposure swing: the within-athlete 10th-to-90th percentile spread,
    # averaged over athletes. Demeaning first keeps this a *within-person* range rather
    # than a between-person one.
    exp_series = df[[ATHLETE_ID, h.exposure]].replace([np.inf, -np.inf], np.nan).dropna()
    if not exp_series.empty:
        centred = exp_series[h.exposure] - exp_series.groupby(ATHLETE_ID)[h.exposure].transform("mean")
        p10, p90 = np.percentile(centred, [10, 90])
        realistic_swing = float(p90 - p10)
    else:  # pragma: no cover
        realistic_swing = float("nan")

    finding = Finding(
        hypothesis_id=h.id,
        family=h.family,
        question=h.question,
        verdict=Verdict.INCONCLUSIVE,  # set by _classify once p_adjusted is known
        outcome=h.outcome,
        exposure=h.exposure,
        covariates=list(covariates),
        coef=e.coef,
        se=e.se,
        ci_low=e.ci_low,
        ci_high=e.ci_high,
        p_value=e.p_value,
        p_adjusted=float("nan"),
        n_obs=e.n_obs,
        n_athletes=e.n_clusters,
        r2_within=fit.r2_within,
        effect_per_exposure_sd=e.coef_per_exposure_sd,
        pct_of_outcome_sd=e.pct_of_outcome_sd,
        mde_80=e.mde_80,
        rope=rope,
        rope_sd_frac=h.rope_sd_frac,
        equivalence_p=equivalence_p,
        plain_language="",
        quotable_claim="",
        confounding_note=h.confounding_note,
        pmids=list(h.pmids),
        realistic_swing=realistic_swing,
        warnings=warnings,
    )

    if with_dose_response and h.dose_bins:
        try:
            dr = est.dose_response(df, h.outcome, h.exposure, h.dose_bins)
            finding.dose_response = dr.to_dict(orient="records")
            finding.dose_monotonic = bool(dr.attrs.get("monotonic"))
        except (ValueError, KeyError) as exc:  # pragma: no cover
            log.debug("dose-response failed for %s: %s", h.id, exc)

    if with_negative_control:
        try:
            finding.negative_control = est.permutation_negative_control(
                df, h.outcome, h.exposure, covariates, n_permutations=n_permutations
            )
        except (ValueError, KeyError) as exc:  # pragma: no cover
            log.debug("negative control failed for %s: %s", h.id, exc)

    return finding


def _classify(f: Finding, h: Hypothesis) -> Verdict:
    """Cross (detectably nonzero?) with (bounded below the actionable threshold?).

    The two questions are independent, and at this sample size they routinely disagree:
    an effect can be certain to exist and still be far too small to change a decision.
    """
    alpha = settings.alpha
    detectable = f.p_adjusted < alpha
    bounded_trivial = np.isfinite(f.equivalence_p) and f.equivalence_p < alpha

    if bounded_trivial:
        # The whole CI sits inside the region of practical equivalence.
        return Verdict.DETECTABLE_BUT_TRIVIAL if detectable else Verdict.NEGLIGIBLE

    if detectable:
        expected = h.expected_sign
        if expected is not None and np.sign(f.coef) != expected:
            return Verdict.DIRECTION_REVERSED
        return Verdict.SUPPORTED

    # Neither reject zero nor bound the effect: the design simply cannot settle this.
    return Verdict.INCONCLUSIVE


def _narrate(f: Finding, h: Hypothesis) -> tuple[str, str]:
    """Build the plain-language summary and the single quotable claim."""
    per = _exposure_label(h.exposure)
    eff = _fmt_effect(f.coef, f.outcome, per)
    ci = _fmt_ci(f.ci_low, f.ci_high, f.outcome)
    n = f"{f.n_obs:,} athlete-days from {f.n_athletes} athletes"
    unit = UNITS.get(f.outcome, "units")

    # "Per unit" is close to meaningless when the unit is one strain point. Restating
    # the effect over a realistic swing in the exposure is what makes it judgeable.
    swing = f.realistic_swing
    swing_effect = f.coef * swing if np.isfinite(swing) else np.nan
    swing_txt = (
        f"Across a realistic swing in {h.exposure.replace('_', ' ')} "
        f"({swing:.3g} units, the 10th-to-90th-percentile range within an athlete), that "
        f"totals {swing_effect:+.3g} {unit}."
        if np.isfinite(swing_effect)
        else ""
    )

    if f.verdict is Verdict.SUPPORTED:
        body = (
            h.plain_template.format(effect=eff, ci=ci, n=n)
            if h.plain_template
            else f"{h.question} Yes — {eff} ({ci}), across {n}."
        )
        claim = (
            f"{body} That is {abs(f.pct_of_outcome_sd):.1f}% of a typical day-to-day "
            f"swing per SD of exposure. {swing_txt}"
        )

    # State the equivalence bound as a fraction of a typical day-to-day swing. In raw
    # per-unit terms it is uninterpretable — "±7.5 ms per unit of acute:chronic ratio"
    # is technically correct and tells a reader nothing.
    bound_pct = 100 * f.rope_sd_frac

    if f.verdict is Verdict.DETECTABLE_BUT_TRIVIAL:
        claim = (
            f"{h.question} The effect is real but too small to act on. It is "
            f"statistically solid — {eff} ({ci}), Holm-adjusted p={f.p_adjusted:.2g} "
            f"across {n} — and an equivalence test simultaneously bounds it below "
            f"{bound_pct:.0f}% of a typical day-to-day swing (p={f.equivalence_p:.2g}). "
            f"{swing_txt} Believe it exists; do not change anything because of it."
        )

    elif f.verdict is Verdict.NEGLIGIBLE:
        claim = (
            f"{h.question} No — and this is a positive finding, not a failed search. "
            f"The effect cannot be distinguished from zero (Holm-adjusted "
            f"p={f.p_adjusted:.2g}) *and* an equivalence test bounds it below "
            f"{bound_pct:.0f}% of a typical day-to-day swing "
            f"(p={f.equivalence_p:.2g}, {ci}), across {n}. {swing_txt} "
            f"Both halves matter: the effect is not merely undetected, it is ruled out "
            f"as a practical influence."
        )

    elif f.verdict is Verdict.DIRECTION_REVERSED:
        claim = (
            f"{h.question} The data show the *opposite* of the expected direction: "
            f"{eff} ({ci}), Holm-adjusted p={f.p_adjusted:.2g}, across {n}. {swing_txt} "
            f"Treat this as a flag to investigate the data or the hypothesis, not a "
            f"result to act on."
        )

    else:  # INCONCLUSIVE
        claim = (
            f"{h.question} Undetermined — and that is the honest answer, not a null. "
            f"The estimate is {eff} ({ci}) across {n}, consistent with no effect, but "
            f"this design could only reliably detect {f.mde_80:.3g} {unit} per {per} or "
            f"larger — wider than the {bound_pct:.0f}%-of-a-typical-swing threshold that "
            f"would make it matter. A real, actionable effect could be hiding here."
        )

    plain = f"[{VERDICT_PHRASING[f.verdict]}] {claim}"
    return plain, claim


def run_family(
    df: pd.DataFrame,
    hypotheses: Sequence[Hypothesis] = HYPOTHESES,
    *,
    with_negative_controls: bool = True,
    n_permutations: int = 200,
) -> list[Finding]:
    """Run the whole pre-registered family with family-wise error control.

    Negative controls are run only for results that survive correction, because a
    permutation test on an already-null result tells us nothing and costs the most time.
    """
    findings: list[Finding] = []
    for h in hypotheses:
        f = run_hypothesis(df, h, with_negative_control=False)
        if f is not None:
            findings.append(f)

    if not findings:
        return []

    adjusted = est.holm_bonferroni([f.p_value for f in findings])
    for f, p_adj in zip(findings, adjusted):
        f.p_adjusted = float(p_adj)
        h = next(x for x in hypotheses if x.id == f.hypothesis_id)
        f.verdict = _classify(f, h)
        f.plain_language, f.quotable_claim = _narrate(f, h)

    if with_negative_controls:
        for f in findings:
            if f.verdict not in (Verdict.SUPPORTED, Verdict.DIRECTION_REVERSED):
                continue
            h = next(x for x in hypotheses if x.id == f.hypothesis_id)
            try:
                nc = est.permutation_negative_control(
                    df, f.outcome, f.exposure, tuple(f.covariates), n_permutations=n_permutations
                )
                f.negative_control = nc
                if not nc["passes"]:
                    f.warnings.append(
                        "Negative control FAILED: a shuffled exposure reproduces an effect "
                        "of similar size, so this may be an artifact of trend rather than a "
                        "day-to-day relationship."
                    )
            except (ValueError, KeyError) as exc:  # pragma: no cover
                log.debug("negative control failed for %s: %s", f.hypothesis_id, exc)

    return findings


# --------------------------------------------------------------------------------------
# Reporting helpers
# --------------------------------------------------------------------------------------


def findings_to_frame(findings: Sequence[Finding]) -> pd.DataFrame:
    """Tabular view for the dashboard and for eyeballing during development."""
    return pd.DataFrame(
        [
            {
                "id": f.hypothesis_id,
                "family": f.family,
                "verdict": f.verdict.value,
                "outcome": f.outcome,
                "exposure": f.exposure,
                "coef": round(f.coef, 4),
                "ci": f"[{f.ci_low:+.3g}, {f.ci_high:+.3g}]",
                "p_raw": f.p_value,
                "p_holm": f.p_adjusted,
                "pct_of_sd": round(f.pct_of_outcome_sd, 2),
                "over_swing": round(f.coef * f.realistic_swing, 3),
                "rope": round(f.rope, 4),
                "mde80": round(f.mde_80, 4),
                "n": f.n_obs,
                "athletes": f.n_athletes,
                "neg_control": (
                    None if f.negative_control is None else f.negative_control.get("passes")
                ),
            }
            for f in findings
        ]
    )


def family_summary(findings: Sequence[Finding]) -> dict:
    """Counts by verdict, plus the honesty statistics worth putting on a slide."""
    counts = {v.value: 0 for v in Verdict}
    for f in findings:
        counts[f.verdict.value] += 1
    n = max(len(findings), 1)

    detectable = sum(1 for f in findings if f.p_adjusted < settings.alpha)
    actionable = counts[Verdict.SUPPORTED.value] + counts[Verdict.DIRECTION_REVERSED.value]

    return {
        "n_hypotheses": len(findings),
        "verdicts": counts,
        # The gap between these two numbers is the whole argument: at this sample size,
        # "statistically detectable" and "worth doing something about" are not the same
        # question, and reporting only the first is how dashboards mislead.
        "n_statistically_detectable": detectable,
        "n_practically_actionable": actionable,
        "pct_detectable_but_not_actionable": round(
            100 * max(detectable - actionable, 0) / n, 1
        ),
        "pct_no_actionable_effect": round(100 * (len(findings) - actionable) / n, 1),
        "alpha": settings.alpha,
        "correction": "Holm-Bonferroni, family-wise",
        "inference": "within-athlete fixed effects, cluster-robust SE on athlete, t(G-1)",
        "equivalence": "TOST against a per-hypothesis region of practical equivalence",
    }


def score_audit(findings: Sequence[Finding]) -> dict | None:
    """Compare a composite score against the raw signal it claims to summarise.

    If load demonstrably moves HRV but demonstrably does *not* move the recovery score,
    the composite is discarding information its own inputs contain. That is a concrete,
    testable indictment of a proprietary metric rather than a vibe.
    """
    by_id = {f.hypothesis_id: f for f in findings}
    raw, composite = by_id.get("A1_strain_to_hrv"), by_id.get("C1_strain_to_recovery")
    if raw is None or composite is None:
        return None

    # The comparison that matters is *detectability*, not the practical-relevance label.
    # If the same exposure is detectable in the raw signal and undetectable in the
    # composite built from it, the composite is throwing information away — regardless
    # of whether either effect is large enough to act on.
    raw_detectable = raw.p_adjusted < settings.alpha
    composite_detectable = composite.p_adjusted < settings.alpha
    discards = raw_detectable and not composite_detectable

    ratio = (
        abs(composite.pct_of_outcome_sd) / abs(raw.pct_of_outcome_sd)
        if raw.pct_of_outcome_sd
        else np.nan
    )

    return {
        "raw_signal": {
            "id": raw.hypothesis_id,
            "outcome": raw.outcome,
            "verdict": raw.verdict.value,
            "coef": raw.coef,
            "p_holm": raw.p_adjusted,
            "pct_of_sd": raw.pct_of_outcome_sd,
            "detectable": bool(raw_detectable),
        },
        "composite": {
            "id": composite.hypothesis_id,
            "outcome": composite.outcome,
            "verdict": composite.verdict.value,
            "coef": composite.coef,
            "p_holm": composite.p_adjusted,
            "pct_of_sd": composite.pct_of_outcome_sd,
            "detectable": bool(composite_detectable),
        },
        "signal_retention_ratio": None if not np.isfinite(ratio) else round(float(ratio), 3),
        "composite_discards_load_signal": bool(discards),
        "interpretation": (
            f"Yesterday's training load is detectable in raw HRV (Holm p="
            f"{raw.p_adjusted:.2g}) but not in the composite recovery score (Holm p="
            f"{composite.p_adjusted:.2g}), even though the composite is built from that "
            f"same physiology. The composite retains roughly "
            f"{0 if not np.isfinite(ratio) else ratio:.0%} of the load signal present in "
            f"its own input. Whatever the score is summarising, it is not yesterday's load."
            if discards
            else "The composite and the raw signal respond consistently to this exposure."
        ),
    }


def describe_column(name: str) -> str:
    doc = COLUMN_DOCS.get(name)
    if doc is None:
        return f"{name} (derived feature; see cnscoach.data.features)"
    return f"{doc.name} [{doc.unit}] — {doc.description} (source: {doc.source})"


def athlete_slice(df: pd.DataFrame, athlete_id: str) -> pd.DataFrame:
    """One athlete's rows, for per-person analysis and for grounding the coach."""
    sub = df[df[ATHLETE_ID] == athlete_id]
    if sub.empty:
        raise KeyError(f"No athlete '{athlete_id}' in panel")
    return sub.sort_values("date")
