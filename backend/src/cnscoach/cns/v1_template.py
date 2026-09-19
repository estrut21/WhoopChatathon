"""v1_template — your slot. Copy this file, rename it, put your algorithm in `score`.

This is a working model, not pseudocode: it is registered, it validates, and
`--cns-model v1_template` runs it today. It is deliberately naive (two components,
round-number weights) so that the diff between it and a real model is your algorithm
and nothing else.

Checklist for a model that will pass `CNSResult.validate()`:

  1. Every `Component.contribution` must equal `subscore * weight`.
  2. Weights must sum to exactly 1.0.
  3. Set `available=False` on any component whose input was missing, and hold its
     subscore at neutral (50) rather than silently dropping it — a score computed from
     four of six inputs is not the same score.
  4. Set `calibrating=True` when the personal baseline is too young to compare against.
     Returning a confident number from three days of history is the failure mode this
     whole project exists to avoid.

Ideas worth trying, all computable from the features already in the panel:

  * **Reactivity, not level.** Score the *change* in HRV relative to the load that
    caused it — `hrv_pct_dev / day_strain_lag1` — so an athlete who absorbs a hard day
    without an autonomic dip scores better than one who collapses after an easy one.
    This is the ratio Strain cannot express.
  * **Parasympathetic saturation.** Very high HRV alongside very low RHR can indicate
    non-functional overreaching rather than freshness. A strictly monotone
    "more HRV is better" mapping misses it; a penalty above roughly +2 SD catches it.
  * **Hysteresis.** Weight the last three days' deficits with a decay, so the score has
    memory of a hard block instead of resetting every morning.
  * **Per-athlete weights.** Fit the component weights against each athlete's own
    next-day performance proxy; `cnscoach.cns.calibrate` does the fitting.
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
    z_to_subscore,
)
from cnscoach.cns.registry import register

WEIGHTS: dict[str, float] = {
    "autonomic": 0.70,
    "load": 0.30,
}


@register
class TemplateV1:
    name = "v1_template"
    version = "0.0.1"
    description = "Minimal two-component example. Copy this to start your own model."

    weights = WEIGHTS

    def score(self, ctx: ScoreContext) -> CNSResult:
        hrv_z = ctx.value("ln_hrv_z")
        strain_yesterday = ctx.value("day_strain_lag1")

        autonomic = Component(
            name="autonomic",
            label="Autonomic balance",
            raw_value=ctx.value("hrv_pct_dev"),
            subscore=z_to_subscore(hrv_z, higher_is_better=True),
            weight=WEIGHTS["autonomic"],
            contribution=0.0,
            unit="% vs baseline",
            rationale="HRV against personal baseline.",
            inputs=("ln_hrv_z", "hrv_pct_dev"),
            available=np.isfinite(hrv_z),
        )

        # Linear decay from a full score at zero load to zero at the top of the scale.
        load_sub = (
            50.0 if not np.isfinite(strain_yesterday) else float(np.clip(100 - 4.8 * strain_yesterday, 0, 100))
        )
        load = Component(
            name="load",
            label="Yesterday's load",
            raw_value=strain_yesterday,
            subscore=load_sub,
            weight=WEIGHTS["load"],
            contribution=0.0,
            unit="strain",
            direction="lower_is_better",
            rationale="Linear penalty on yesterday's cardiovascular load.",
            inputs=("day_strain_lag1",),
            available=np.isfinite(strain_yesterday),
        )

        components = [replace(c, contribution=c.subscore * c.weight) for c in (autonomic, load)]
        total = sum(c.contribution for c in components)

        history_days = ctx.days_of_history()
        comp = completeness({"hrv_z": hrv_z, "strain": strain_yesterday})

        result = CNSResult(
            score=round(float(total), 1),
            band=band_for(total),
            components=components,
            model_name=self.name,
            model_version=self.version,
            confidence=round(float(np.clip(0.5 * comp + 0.5 * min(history_days / 56, 1), 0, 1)), 3),
            data_completeness=round(comp, 3),
            baseline_days_available=history_days,
            calibrating=history_days < MIN_BASELINE_DAYS or not np.isfinite(hrv_z),
            date=str(ctx.date.date()) if hasattr(ctx.date, "date") else str(ctx.date),
            athlete_id=ctx.athlete_id,
            caveats=["Template model — illustrative only, not tuned against anything."],
        )
        result.validate()
        return result
