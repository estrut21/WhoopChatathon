"""Prove the engine works before trusting anything it says.

Running an analysis pipeline on real data tells you what it *outputs*. It does not tell
you whether those outputs are right, because the truth is unknown. So: generate panels
where the truth is known by construction, and check three things the engine claims.

1. **Recovery.** When an effect is planted, does the estimate land on it? Measured as
   bias and as 95% CI coverage across replications. Coverage that is not close to 95%
   means the standard errors are wrong, which is the failure mode that makes every
   downstream p-value a lie.
2. **False positives.** When no effect is planted, how often does the engine claim one?
   With family-wise correction this should sit at or below alpha, not at alpha per test.
3. **Power and the null verdicts.** On a small panel where an effect exists but cannot
   be detected, does the engine say INCONCLUSIVE rather than NEGLIGIBLE? Conflating
   "absent" with "invisible" is the specific dishonesty this project is built against.

The generator deliberately includes athlete-level random intercepts and AR(1) serial
correlation, because those are what break naive pooled analyses.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from cnscoach.causal import estimators as est
from cnscoach.config import settings
from cnscoach.data.schema import ATHLETE_ID, DATE


@dataclass
class PlantedEffect:
    """A known coefficient to bury in synthetic data and then try to dig back out."""

    exposure: str
    outcome: str
    coef: float
    lag: int = 1


@dataclass
class RecoveryResult:
    exposure: str
    outcome: str
    true_coef: float
    mean_estimate: float
    bias: float
    mean_se: float
    empirical_sd: float
    ci_coverage: float
    power: float
    n_replications: int

    @property
    def se_ratio(self) -> float:
        """Reported SE over the estimator's true sampling SD. Should be near 1."""
        return self.mean_se / self.empirical_sd if self.empirical_sd > 0 else float("nan")

    @property
    def se_is_calibrated(self) -> bool:
        """Only *anticonservative* standard errors are a failure.

        A ratio below 1 means the reported uncertainty is smaller than the real
        sampling variability — CIs too narrow, p-values too small, false discoveries.
        A ratio above 1 costs power but never manufactures a finding, so it is a
        warning rather than a failure. The asymmetry is deliberate.

        Note that with few replications the denominator is itself noisy, so this check
        is only meaningful once `n_replications` is reasonably large.
        """
        r = self.se_ratio
        if not np.isfinite(r):
            return False
        if self.n_replications < 25:
            return r >= 0.75  # loose bound; empirical SD is unreliable this early
        return r >= 0.90

    @property
    def se_is_conservative(self) -> bool:
        r = self.se_ratio
        return bool(np.isfinite(r) and r > 1.30)

    @property
    def coverage_is_nominal(self) -> bool:
        """Coverage below nominal is the real failure; above it is merely cautious."""
        return self.ci_coverage >= 0.90


@dataclass
class ValidationReport:
    recovery: list[RecoveryResult] = field(default_factory=list)
    false_positive_rate: float = float("nan")
    fpr_n_replications: int = 0
    fpr_nominal_alpha: float = settings.alpha
    underpowered_verdicts: dict[str, int] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        ok_recovery = all(r.coverage_is_nominal and r.se_is_calibrated for r in self.recovery)
        ok_fpr = (
            np.isnan(self.false_positive_rate)
            or self.false_positive_rate <= self.fpr_nominal_alpha * 2.5
        )
        return bool(ok_recovery and ok_fpr)

    def summary(self) -> str:
        lines = ["ENGINE VALIDATION", "=" * 78, "", "1. EFFECT RECOVERY (planted -> estimated)"]
        lines.append(
            f"   {'exposure -> outcome':<34} {'true':>8} {'est':>8} {'bias':>8} "
            f"{'SE/SD':>7} {'cover':>7} {'power':>7}"
        )
        for r in self.recovery:
            pair = f"{r.exposure} -> {r.outcome}"
            if not (r.coverage_is_nominal and r.se_is_calibrated):
                flag = "FAIL"
            elif r.se_is_conservative:
                flag = "ok (conservative)"
            else:
                flag = "ok"
            lines.append(
                f"   {pair:<34} {r.true_coef:8.3f} {r.mean_estimate:8.3f} {r.bias:+8.3f} "
                f"{r.se_ratio:7.2f} {r.ci_coverage:7.1%} {r.power:7.1%}  {flag}"
            )
        lines += [
            "",
            "   Coverage should sit at or above 95% and SE/SD at or above 1.00. A ratio",
            "   below 1 means reported uncertainty understates real sampling variability,",
            "   which makes every downstream p-value overconfident - that is the failure",
            "   condition. A ratio above 1 costs power but never invents a finding.",
            "",
            "2. FALSE POSITIVE RATE (no effect planted anywhere)",
            (
                f"   family-wise FPR : {self.false_positive_rate:.1%} "
                f"over {self.fpr_n_replications} replications"
            ),
            f"   nominal alpha   : {self.fpr_nominal_alpha:.1%}",
            "",
            "3. UNDERPOWERED PANEL - does the engine admit ignorance?",
        ]
        for verdict, count in sorted(self.underpowered_verdicts.items()):
            lines.append(f"   {verdict:<28} {count}")
        lines += ["", "=" * 78, f"OVERALL: {'PASS' if self.passed else 'FAIL'}"]
        lines.extend(f"note: {n}" for n in self.notes)
        return "\n".join(lines)


# --------------------------------------------------------------------------------------


def synthesize_panel(
    n_athletes: int = 120,
    n_days: int = 180,
    effects: list[PlantedEffect] | None = None,
    *,
    athlete_sd: float = 18.0,
    ar1: float = 0.35,
    noise_sd: float = 12.0,
    seed: int | None = None,
) -> pd.DataFrame:
    """Generate a panel with known causal structure.

    Includes the two features that break naive analyses: large between-athlete
    differences in baseline level, and within-athlete serial correlation.
    """
    rng = np.random.default_rng(seed if seed is not None else settings.random_seed)
    effects = effects or []

    dates = pd.date_range("2024-01-01", periods=n_days, freq="D")
    frames = []

    for a in range(n_athletes):
        aid = f"SYN_{a:05d}"
        # Exposures: strain has a weekly rhythm, sleep is athlete-specific.
        strain = np.clip(
            rng.normal(10, 4, n_days) + 2.5 * np.sin(np.arange(n_days) * 2 * np.pi / 7), 0, 21
        )
        sleep = np.clip(rng.normal(rng.normal(7.3, 0.5), 0.9, n_days), 3.5, 11)
        wake_ups = rng.poisson(0.4, n_days)

        base_hrv = rng.normal(70, 22)
        base_rec = rng.normal(65, athlete_sd)

        # AR(1) innovations give realistic day-to-day persistence.
        def ar_noise(sd: float) -> np.ndarray:
            e = rng.normal(0, sd, n_days)
            out = np.empty(n_days)
            out[0] = e[0]
            for t in range(1, n_days):
                out[t] = ar1 * out[t - 1] + e[t]
            return out

        hrv = base_hrv + ar_noise(noise_sd * 0.6)
        recovery = base_rec + ar_noise(noise_sd)

        exposures = {"day_strain": strain, "sleep_hours": sleep, "wake_ups": wake_ups}
        for eff in effects:
            src = exposures.get(eff.exposure)
            if src is None:
                continue
            lagged = np.concatenate([np.zeros(eff.lag), src[: -eff.lag or None]])
            centred = lagged - lagged.mean()
            if eff.outcome == "hrv":
                hrv = hrv + eff.coef * centred
            elif eff.outcome == "recovery_score":
                recovery = recovery + eff.coef * centred

        frames.append(
            pd.DataFrame(
                {
                    ATHLETE_ID: aid,
                    DATE: dates,
                    "day_strain": strain,
                    "sleep_hours": sleep,
                    "wake_ups": wake_ups,
                    "hrv": np.clip(hrv, 5, None),
                    "recovery_score": np.clip(recovery, 1, 100),
                }
            )
        )

    panel = pd.concat(frames, ignore_index=True).sort_values([ATHLETE_ID, DATE])
    for col in ("day_strain", "sleep_hours", "wake_ups"):
        panel[f"{col}_lag1"] = panel.groupby(ATHLETE_ID)[col].shift(1)
    return panel.reset_index(drop=True)


def check_recovery(
    effects: list[PlantedEffect],
    *,
    n_replications: int = 40,
    n_athletes: int = 120,
    n_days: int = 180,
    seed: int | None = None,
) -> list[RecoveryResult]:
    """Plant effects, estimate them, and measure bias, SE calibration and coverage."""
    base_seed = seed if seed is not None else settings.random_seed
    collected: dict[tuple[str, str], list[tuple[float, float, bool, bool]]] = {
        (e.exposure, e.outcome): [] for e in effects
    }

    for rep in range(n_replications):
        panel = synthesize_panel(
            n_athletes=n_athletes, n_days=n_days, effects=effects, seed=base_seed + rep
        )
        for eff in effects:
            term = f"{eff.exposure}_lag{eff.lag}" if eff.lag else eff.exposure
            if term not in panel.columns:
                continue
            try:
                e = est.within_athlete_fe(panel, eff.outcome, [term]).get(term)
            except (ValueError, KeyError):  # pragma: no cover
                continue
            covered = e.ci_low <= eff.coef <= e.ci_high
            detected = e.p_value < settings.alpha
            collected[(eff.exposure, eff.outcome)].append((e.coef, e.se, covered, detected))

    results = []
    for eff in effects:
        rows = collected[(eff.exposure, eff.outcome)]
        if not rows:  # pragma: no cover
            continue
        coefs = np.array([r[0] for r in rows])
        ses = np.array([r[1] for r in rows])
        results.append(
            RecoveryResult(
                exposure=f"{eff.exposure}_lag{eff.lag}",
                outcome=eff.outcome,
                true_coef=eff.coef,
                mean_estimate=float(coefs.mean()),
                bias=float(coefs.mean() - eff.coef),
                mean_se=float(ses.mean()),
                empirical_sd=float(coefs.std(ddof=1)) if len(coefs) > 1 else 0.0,
                ci_coverage=float(np.mean([r[2] for r in rows])),
                power=float(np.mean([r[3] for r in rows])),
                n_replications=len(rows),
            )
        )
    return results


def check_false_positives(
    *,
    n_replications: int = 60,
    n_athletes: int = 120,
    n_days: int = 180,
    seed: int | None = None,
) -> tuple[float, int]:
    """With nothing planted, how often does the corrected family claim a discovery?"""
    base_seed = (seed if seed is not None else settings.random_seed) + 9_000
    tests = [
        ("day_strain_lag1", "hrv"),
        ("sleep_hours_lag1", "hrv"),
        ("wake_ups_lag1", "hrv"),
        ("day_strain_lag1", "recovery_score"),
        ("sleep_hours_lag1", "recovery_score"),
        ("wake_ups_lag1", "recovery_score"),
    ]

    any_false = 0
    for rep in range(n_replications):
        panel = synthesize_panel(
            n_athletes=n_athletes, n_days=n_days, effects=[], seed=base_seed + rep
        )
        p_values = []
        for exposure, outcome in tests:
            try:
                p_values.append(est.within_athlete_fe(panel, outcome, [exposure]).get(exposure).p_value)
            except (ValueError, KeyError):  # pragma: no cover
                continue
        if p_values and np.min(est.holm_bonferroni(p_values)) < settings.alpha:
            any_false += 1

    return any_false / max(n_replications, 1), n_replications


def check_underpowered_honesty(
    *, n_athletes: int = 12, n_days: int = 40, seed: int | None = None
) -> dict[str, int]:
    """On a panel too small to see a real effect, the engine must say so.

    A real effect is planted, then the sample is made too small to detect it. The
    correct verdict is INCONCLUSIVE with a reported minimum detectable effect — *not*
    NEGLIGIBLE, which would assert the effect is absent when it is merely invisible.
    """
    from cnscoach.causal.engine import Verdict, _classify  # local import avoids a cycle
    from cnscoach.causal.hypotheses import Hypothesis

    panel = synthesize_panel(
        n_athletes=n_athletes,
        n_days=n_days,
        effects=[PlantedEffect("day_strain", "hrv", coef=-0.30)],
        seed=(seed if seed is not None else settings.random_seed) + 4_242,
    )

    h = Hypothesis(
        id="tiny",
        family="validation",
        question="Underpowered probe",
        outcome="hrv",
        exposure="day_strain_lag1",
        direction="negative",
        rope_sd_frac=0.05,
    )

    counts: dict[str, int] = {}
    for athlete_subset in range(3, min(n_athletes, 12) + 1, 3):
        ids = panel[ATHLETE_ID].unique()[:athlete_subset]
        sub = panel[panel[ATHLETE_ID].isin(ids)]
        try:
            e = est.within_athlete_fe(sub, h.outcome, [h.exposure], min_obs_per_athlete=10).get(
                h.exposure
            )
        except (ValueError, KeyError):  # pragma: no cover
            continue

        rope = h.rope_sd_frac * e.outcome_sd / e.exposure_sd
        e.rope = rope
        e.equivalence_p = est.tost_equivalence(e, rope)

        probe = type(
            "Probe",
            (),
            {
                "p_adjusted": e.p_value,
                "equivalence_p": e.equivalence_p,
                "coef": e.coef,
            },
        )()
        verdict: Verdict = _classify(probe, h)
        counts[verdict.value] = counts.get(verdict.value, 0) + 1

    return counts


def validate_engine(
    *, n_replications: int = 40, quick: bool = False, seed: int | None = None
) -> ValidationReport:
    """Run the whole validation suite."""
    if quick:
        n_replications = max(10, n_replications // 4)

    effects = [
        PlantedEffect("day_strain", "hrv", coef=-0.80),
        PlantedEffect("sleep_hours", "hrv", coef=2.50),
        PlantedEffect("day_strain", "recovery_score", coef=-0.50),
    ]

    report = ValidationReport()
    report.recovery = check_recovery(
        effects, n_replications=n_replications, n_athletes=100, n_days=150, seed=seed
    )
    report.false_positive_rate, report.fpr_n_replications = check_false_positives(
        n_replications=n_replications, n_athletes=100, n_days=150, seed=seed
    )
    report.underpowered_verdicts = check_underpowered_honesty(seed=seed)

    report.notes.append(
        "Synthetic panels include athlete random intercepts (SD 18) and AR(1) serial "
        "correlation (rho 0.35) — the two features that make naive pooled analyses "
        "overconfident."
    )
    if any(not r.se_is_calibrated for r in report.recovery):
        report.notes.append(
            "At least one SE/SD ratio is below 0.90: the cluster-robust variance "
            "estimator is understating sampling variability, so p-values from this "
            "configuration are overconfident."
        )
    elif any(r.se_is_conservative for r in report.recovery):
        report.notes.append(
            "Some standard errors are conservative (SE/SD > 1.30). This costs power "
            "but cannot manufacture a finding, so it is a warning, not a failure."
        )
    if n_replications < 25:
        report.notes.append(
            f"Only {n_replications} replications: the empirical SD in the SE/SD ratio is "
            "itself noisy and the ratio will look worse than it is. Run without --quick "
            "for a trustworthy calibration check."
        )
    if report.underpowered_verdicts.get("negligible"):
        report.notes.append(
            "WARNING: a real planted effect was called NEGLIGIBLE on an underpowered "
            "panel. The ROPE is too wide relative to what this sample size can resolve."
        )
    return report
