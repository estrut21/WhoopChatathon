"""v0_autonomic - the shipped default CNS readiness score.

The argument for replacing Strain
---------------------------------
Strain is a single monotone function of cardiovascular work: it rises when the heart
rate integral rises and does nothing else. It cannot distinguish an athlete who is
absorbing that work from one who is drowning in it, because it never looks at the
response. A readiness metric has to be a *ratio of load to tolerance*, and tolerance is
observable in the autonomic markers the device already records.

So this score is built from six components, each interpretable in its own right, each
weighted in the open:

  autonomic_balance   0.35   ln-HRV vs personal 28d baseline
  chronotropic_load   0.20   resting HR vs personal baseline (inverted)
  load_balance        0.15   acute:chronic workload ratio, penalised both ways
  sleep_debt          0.15   accumulated 7-day deficit vs personal need
  sleep_quality       0.08   restorative fraction (SWS + REM) vs personal baseline
  systemic_stress     0.07   respiratory rate and skin-temperature excursions

Where the weights come from, honestly
-------------------------------------
They are a *defensible prior*, not a fitted result. The literature supports the
ordering - vagally-mediated HRV is the most responsive non-invasive marker of autonomic
recovery status, resting HR is second, and the load-balance and sleep terms are
modulators rather than primary signals - but it does not pin the numbers down to two
decimal places, and pretending otherwise would be the same sin the incumbent metrics
commit.

`cnscoach.cns.calibrate` refits these weights against any outcome you can define, and
reports the refit next to the prior with out-of-sample R2 for both, so "the fit helped"
is checkable rather than assumed.

A note on self-validation
-------------------------
`load_balance` consumes lagged strain. That means this score will correlate with
yesterday's training load partly *by construction*. `cnscoach.cns.base.circularity_report`
exists to catch exactly that, and every component below declares its inputs so the check
can work. Do not cite a load-response comparison without running it.

References (see `cnscoach.evidence.corpus` for full records):
  PMID 37754967 - exercise cardiac load, ANS recovery and next-day performance
  PMID 31642195 - dose-dependent ANS adaptation to training load
  PMID 33202732 - HRV response across a training cycle
  PMID 35344471 - training monotony/strain and overreaching
  PMID 30300066 - lnRMSSD interpretation caveats
  PMID 35409591 - central vs peripheral fatigue
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from cnscoach.cns.base import (
    MIN_BASELINE_DAYS,
    CNSResult,
    Component,
    ScoreContext,
    band_for,
    completeness,
    u_shaped_subscore,
    z_to_subscore,
)
from cnscoach.cns.registry import register

WEIGHTS: dict[str, float] = {
    "autonomic_balance": 0.35,
    "chronotropic_load": 0.20,
    "load_balance": 0.15,
    "sleep_debt": 0.15,
    "sleep_quality": 0.08,
    "systemic_stress": 0.07,
}


@register
class AutonomicV0:
    name = "v0_autonomic"
    version = "0.1.0"
    description = (
        "Literature-weighted autonomic readiness score. Load measured against personal "
        "tolerance rather than in absolute terms. Every component decomposable."
    )

    weights = WEIGHTS

    def score(self, ctx: ScoreContext) -> CNSResult:
        caveats: list[str] = []
        history_days = ctx.days_of_history()

        # --- 1. Autonomic balance ---------------------------------------------------
        # ln-HRV z against the athlete's own rolling baseline. The single most
        # responsive non-invasive marker of parasympathetic recovery status.
        hrv_z = ctx.value("ln_hrv_z")
        hrv_pct = ctx.value("hrv_pct_dev")
        autonomic = Component(
            name="autonomic_balance",
            label="Autonomic balance",
            raw_value=hrv_pct,
            subscore=z_to_subscore(hrv_z, higher_is_better=True),
            weight=WEIGHTS["autonomic_balance"],
            contribution=0.0,
            unit="% vs baseline",
            rationale=(
                "Overnight HRV relative to this athlete's own 28-day baseline, computed "
                "in log space because RMSSD is log-normal and raw means are pulled "
                "around by high outliers."
            ),
            pmids=("37754967", "31642195", "30300066"),
            inputs=("ln_hrv_z", "hrv_pct_dev"),
            available=np.isfinite(hrv_z),
        )

        # --- 2. Chronotropic load ---------------------------------------------------
        rhr_z = ctx.value("resting_heart_rate_z")
        rhr_pct = ctx.value("rhr_pct_dev")
        chronotropic = Component(
            name="chronotropic_load",
            label="Chronotropic load",
            raw_value=rhr_pct,
            subscore=z_to_subscore(rhr_z, higher_is_better=False),
            weight=WEIGHTS["chronotropic_load"],
            contribution=0.0,
            unit="% vs baseline",
            direction="lower_is_better",
            rationale=(
                "Elevated resting heart rate against personal baseline indicates "
                "incomplete autonomic recovery, and moves more slowly than HRV."
            ),
            pmids=("37754967", "31642195"),
            inputs=("resting_heart_rate_z", "rhr_pct_dev"),
            available=np.isfinite(rhr_z),
        )

        # --- 3. Load balance --------------------------------------------------------
        # Both directions are penalised: a spike is an overreaching/injury risk, and a
        # collapse is detraining. A metric that only punishes high load implies rest is
        # always free, which is false for an athlete in a training block.
        acwr = ctx.value("acwr")
        load = Component(
            name="load_balance",
            label="Load balance (ACWR)",
            raw_value=acwr,
            subscore=u_shaped_subscore(acwr, optimal=1.0, tolerance=0.3),
            weight=WEIGHTS["load_balance"],
            contribution=0.0,
            unit="ratio",
            direction="optimum_at_1.0",
            rationale=(
                "Acute (7d) over chronic (28d) exponentially-weighted load. Penalised "
                "in both directions - a spike risks overreaching, a collapse is "
                "detraining."
            ),
            pmids=("35344471", "33202732"),
            inputs=("acwr",),
            available=np.isfinite(acwr),
        )

        # --- 4. Sleep debt ----------------------------------------------------------
        debt = ctx.value("sleep_debt_7d")
        # Five hours of accumulated deficit over a week is treated as a full penalty.
        debt_sub = 100.0 if not np.isfinite(debt) else float(np.clip(100 - 20 * debt, 0, 100))
        sleep_debt = Component(
            name="sleep_debt",
            label="Sleep debt (7d)",
            raw_value=debt,
            subscore=50.0 if not np.isfinite(debt) else debt_sub,
            weight=WEIGHTS["sleep_debt"],
            contribution=0.0,
            unit="h",
            direction="lower_is_better",
            rationale=(
                "Accumulated shortfall against this athlete's own trailing median sleep "
                "need, not a universal 8-hour target."
            ),
            pmids=("35409591",),
            inputs=("sleep_debt_7d",),
            available=np.isfinite(debt),
        )

        # --- 5. Sleep quality -------------------------------------------------------
        pct_restorative = ctx.value("pct_restorative")
        prior_restorative = ctx.prior("pct_restorative", 28)
        if len(prior_restorative) >= 7 and np.isfinite(pct_restorative):
            mu, sd = prior_restorative.mean(), prior_restorative.std()
            rest_z = (pct_restorative - mu) / sd if sd and np.isfinite(sd) and sd > 0 else np.nan
        else:
            rest_z = np.nan
        sleep_quality = Component(
            name="sleep_quality",
            label="Restorative sleep",
            raw_value=pct_restorative,
            subscore=z_to_subscore(rest_z, higher_is_better=True),
            weight=WEIGHTS["sleep_quality"],
            contribution=0.0,
            unit="% deep+REM",
            rationale=(
                "Share of the night in slow-wave and REM sleep, against this athlete's "
                "own distribution. Weighted low because stage estimates from wrist "
                "photoplethysmography are the least reliable input here."
            ),
            pmids=("35409591",),
            inputs=("pct_restorative",),
            available=np.isfinite(rest_z),
        )

        # --- 6. Systemic stress -----------------------------------------------------
        resp_z = ctx.value("respiratory_rate_z")
        skin = ctx.value("skin_temp_deviation")
        penalties = []
        if np.isfinite(resp_z):
            penalties.append(min(abs(resp_z) / 2.0, 1.0) if resp_z > 0 else 0.0)
        if np.isfinite(skin):
            penalties.append(min(abs(skin) / 1.5, 1.0))
        stress_sub = 100.0 - 100.0 * (max(penalties) if penalties else 0.5)
        systemic = Component(
            name="systemic_stress",
            label="Systemic stress",
            raw_value=resp_z if np.isfinite(resp_z) else skin,
            subscore=float(np.clip(stress_sub, 0, 100)),
            weight=WEIGHTS["systemic_stress"],
            contribution=0.0,
            unit="SD / degC",
            direction="lower_is_better",
            rationale=(
                "Respiratory-rate elevation and skin-temperature excursion, the two "
                "illness signals available. Worst-of rather than average, because "
                "either alone is enough reason to back off."
            ),
            pmids=("35409591",),
            inputs=("respiratory_rate_z", "skin_temp_deviation"),
            available=bool(penalties),
        )

        # Fill in each contribution now that every subscore is known, preserving the
        # invariant that contributions sum to the score.
        components = [
            replace(c, contribution=c.subscore * c.weight)
            for c in (autonomic, chronotropic, load, sleep_debt, sleep_quality, systemic)
        ]
        total = sum(c.contribution for c in components)

        # --- honesty accounting ------------------------------------------------------
        comp = completeness(
            {
                "hrv_z": hrv_z,
                "rhr_z": rhr_z,
                "acwr": acwr,
                "sleep_debt": debt,
                "restorative": rest_z,
                "systemic": resp_z if np.isfinite(resp_z) else skin,
            }
        )
        calibrating = history_days < MIN_BASELINE_DAYS or not np.isfinite(hrv_z)

        # Confidence is dominated by whether the baseline is mature enough to compare
        # against, then by how many inputs actually arrived.
        baseline_maturity = float(np.clip(history_days / 56, 0, 1))
        confidence = float(np.clip(0.55 * comp + 0.45 * baseline_maturity, 0, 1))

        missing = [c.label for c in components if not c.available]
        if missing:
            caveats.append(f"Held at neutral for missing inputs: {', '.join(missing)}.")
        if history_days < 56:
            caveats.append(
                f"Baseline is {history_days} days old; it stabilises around 56. Early "
                f"scores move more because the reference is still settling."
            )
        caveats.append(
            "Comparable to this athlete's own history only. Cross-athlete comparison of "
            "this score is not meaningful - the baselines differ."
        )
        caveats.append(
            "Partly built from training load (load_balance, weight 0.15). Do not cite "
            "this score's response to load as validation without a circularity check."
        )
        caveats.append("Not a medical device and not validated against clinical outcomes.")

        result = CNSResult(
            score=round(float(total), 1),
            band=band_for(total),
            components=components,
            model_name=self.name,
            model_version=self.version,
            confidence=round(confidence, 3),
            data_completeness=round(comp, 3),
            baseline_days_available=history_days,
            calibrating=calibrating,
            date=str(ctx.date.date()) if hasattr(ctx.date, "date") else str(ctx.date),
            athlete_id=ctx.athlete_id,
            caveats=caveats,
        )
        result.validate()
        return result
