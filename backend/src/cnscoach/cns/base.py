"""The pluggable CNS readiness score.

This is the replacement slot for opaque proprietary metrics. The contract is
deliberately strict about *explanation*, not about maths: any model may compute the
number however it likes, but it must hand back every component, every weight and every
citation that produced it. A score that cannot be decomposed is not admissible.

Writing a new model
-------------------

    from cnscoach.cns.base import CNSModel, CNSResult, Component, ScoreContext
    from cnscoach.cns.registry import register

    @register
    class MyModel:
        name = "v1_mine"
        version = "1.0.0"
        description = "..."

        def score(self, ctx: ScoreContext) -> CNSResult:
            ...

Then `--cns-model v1_mine` anywhere in the CLI, API or dashboard. Nothing else changes:
the causal engine, the coach and the UI all talk to the protocol, never to a concrete
model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Component:
    """One named contributor to the score.

    `contribution` is what actually moved the final number, so the components always
    reconcile: `sum(c.contribution for c in components) == score`. The dashboard and the
    coach both rely on that invariant, and `CNSResult.validate()` enforces it.
    """

    name: str
    label: str
    raw_value: float
    """The underlying physiological quantity, in its natural unit."""

    subscore: float
    """`raw_value` mapped onto 0-100, where 100 is maximally ready."""

    weight: float
    contribution: float
    """`subscore * weight`. Sums across components to the final score."""

    unit: str = ""
    direction: str = "higher_is_better"
    rationale: str = ""
    pmids: tuple[str, ...] = ()
    available: bool = True
    """False when the input was missing and the component fell back to neutral."""

    inputs: tuple[str, ...] = ()
    """Panel columns this component consumes, transitively.

    Declared so that `circularity_report()` can catch the trap of "proving" a score
    responds to an exposure that is one of its own ingredients. A readiness score built
    partly from lagged training load will of course correlate with lagged training load;
    that is construction, not validation."""

    def __post_init__(self) -> None:
        """Coerce numpy scalars to native Python types.

        `np.isfinite(x)` returns `np.bool_`, not `bool`, and numpy scalars are invisible
        until something tries to serialise them — at which point JSON encoding fails at
        the API boundary rather than here. Model authors should not have to remember
        this, so it is enforced at construction.
        """
        for name in ("raw_value", "subscore", "weight", "contribution"):
            object.__setattr__(self, name, float(getattr(self, name)))
        object.__setattr__(self, "available", bool(self.available))
        object.__setattr__(self, "pmids", tuple(self.pmids))
        object.__setattr__(self, "inputs", tuple(self.inputs))

    def to_dict(self) -> dict:
        d = dict(self.__dict__)
        d["pmids"] = list(self.pmids)
        d["inputs"] = list(self.inputs)
        return d


@dataclass
class CNSResult:
    """A score, with everything needed to argue with it."""

    score: float
    """0-100. Comparable to *this athlete's own* history, never across athletes."""

    band: str
    """A coarse label. Deliberately wider than the numeric precision suggests."""

    components: list[Component]
    model_name: str
    model_version: str

    confidence: float
    """0-1. Driven by input completeness and baseline maturity, not by model certainty."""

    data_completeness: float
    baseline_days_available: int
    calibrating: bool
    """True while the personal baseline is too young for the score to mean anything."""

    date: str | None = None
    athlete_id: str | None = None
    caveats: list[str] = field(default_factory=list)

    def validate(self) -> None:
        """Components must reconcile to the score — the decomposition is the product."""
        total = sum(c.contribution for c in self.components)
        if not np.isclose(total, self.score, atol=0.51):
            raise ValueError(
                f"{self.model_name}: components sum to {total:.2f} but score is "
                f"{self.score:.2f}. A score that cannot be decomposed is not admissible."
            )
        weights = sum(c.weight for c in self.components)
        if not np.isclose(weights, 1.0, atol=1e-6):
            raise ValueError(f"{self.model_name}: weights sum to {weights:.4f}, expected 1.0")

    def explain(self) -> str:
        """Plain-text decomposition. This is what the coach is allowed to quote."""
        if self.calibrating:
            head = (
                f"CNS score unavailable — still calibrating. Only "
                f"{self.baseline_days_available} days of personal baseline are available; "
                f"this model needs at least {MIN_BASELINE_DAYS}. A score computed now "
                f"would be comparing you against a baseline that is mostly noise."
            )
            return head

        header = (
            f"CNS score {self.score:.0f}/100 ({self.band}) "
            f"[{self.model_name} v{self.model_version}, confidence {self.confidence:.0%}]"
        )
        lines = [header, "", "Built from:"]
        for c in sorted(self.components, key=lambda x: -abs(x.contribution)):
            flag = "" if c.available else "  (input missing — held at neutral)"
            lines.append(
                f"  {c.label:<24} {c.subscore:5.1f}/100 x {c.weight:.2f} "
                f"= {c.contribution:5.1f}   [{c.raw_value:+.2f} {c.unit}]{flag}"
            )
        lines.append("")
        lines.append(f"  {'TOTAL':<24} {self.score:5.1f}/100")

        if self.caveats:
            lines.append("")
            lines.append("Caveats:")
            lines.extend(f"  - {c}" for c in self.caveats)
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "band": self.band,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "confidence": self.confidence,
            "data_completeness": self.data_completeness,
            "baseline_days_available": self.baseline_days_available,
            "calibrating": self.calibrating,
            "date": self.date,
            "athlete_id": self.athlete_id,
            "caveats": self.caveats,
            "components": [c.to_dict() for c in self.components],
        }


@dataclass
class ScoreContext:
    """Everything a model may look at for one athlete-day.

    Passing a window rather than a single row is deliberate: a readiness score that
    cannot see history cannot know what is normal *for this person*, and a score
    computed against a population mean is the thing we are trying to replace.
    """

    athlete_id: str
    date: pd.Timestamp
    today: pd.Series
    """The feature row for the scored day."""

    history: pd.DataFrame
    """All prior rows for this athlete, ascending. Never includes `today`."""

    def days_of_history(self) -> int:
        return len(self.history)

    def prior(self, column: str, days: int) -> pd.Series:
        """The last `days` values of `column`, most recent last."""
        if column not in self.history:
            return pd.Series(dtype=float)
        return self.history[column].tail(days)

    def value(self, column: str, default: float = np.nan) -> float:
        v = self.today.get(column, default)
        try:
            v = float(v)
        except (TypeError, ValueError):
            return default
        return default if not np.isfinite(v) else v


MIN_BASELINE_DAYS = 21
"""Below this, a personal baseline is too noisy to score against and models should
return `calibrating=True` rather than a number. WHOOP uses a comparable warm-up; the
difference here is that we say how many days we have and why it is not enough."""


BANDS: tuple[tuple[float, str], ...] = (
    (80, "Primed"),
    (65, "Ready"),
    (50, "Adequate"),
    (35, "Compromised"),
    (0, "Depleted"),
)


def band_for(score: float) -> str:
    for threshold, label in BANDS:
        if score >= threshold:
            return label
    return BANDS[-1][1]


@runtime_checkable
class CNSModel(Protocol):
    """The contract. Implement this and register it; nothing else needs to change."""

    name: str
    version: str
    description: str

    def score(self, ctx: ScoreContext) -> CNSResult: ...


# --------------------------------------------------------------------------------------
# Shared helpers for model authors
# --------------------------------------------------------------------------------------


def z_to_subscore(z: float, *, higher_is_better: bool = True, clip: float = 2.5) -> float:
    """Map a personal z-score onto 0-100, linearly, saturating at +/- `clip` SD.

    Linear rather than a normal CDF on purpose: the CDF compresses the tails, which is
    exactly where a readiness score needs resolution. An athlete at -2.5 SD and one at
    -4 SD are both "very bad" under a CDF; here they are both 0, which is at least
    honest about the saturation instead of implying precision that is not there.
    """
    if not np.isfinite(z):
        return 50.0
    signed = z if higher_is_better else -z
    return float(np.clip(50 + 50 * signed / clip, 0, 100))


def u_shaped_subscore(value: float, *, optimal: float, tolerance: float, floor: float = 0.0) -> float:
    """Penalise deviation from an optimum in either direction.

    For quantities like the acute:chronic workload ratio, where both a spike and a
    collapse are bad and the good region is a plateau rather than a point.
    """
    if not np.isfinite(value):
        return 50.0
    deviation = abs(value - optimal)
    if deviation <= tolerance:
        return 100.0
    excess = (deviation - tolerance) / max(tolerance, 1e-9)
    return float(np.clip(100 - 50 * excess, floor, 100))


def completeness(values: dict[str, float]) -> float:
    """Fraction of required inputs that were actually present."""
    if not values:
        return 0.0
    return float(np.mean([np.isfinite(v) for v in values.values()]))


#: Derived features and the raw columns they are transitively built from. Used to
#: resolve a component's declared inputs down to primitives before checking overlap.
FEATURE_PROVENANCE: dict[str, tuple[str, ...]] = {
    "acwr": ("day_strain",),
    "load_acute": ("day_strain",),
    "load_chronic": ("day_strain",),
    "monotony": ("day_strain",),
    "training_strain_foster": ("day_strain",),
    "ln_hrv_z": ("hrv",),
    "ln_hrv": ("hrv",),
    "hrv_pct_dev": ("hrv",),
    "resting_heart_rate_z": ("resting_heart_rate",),
    "rhr_pct_dev": ("resting_heart_rate",),
    "respiratory_rate_z": ("respiratory_rate",),
    "sleep_debt_7d": ("sleep_hours",),
    "sleep_deficit_h": ("sleep_hours",),
    "sleep_need_personal": ("sleep_hours",),
    "sleep_irregularity": ("sleep_hours",),
    "pct_restorative": ("deep_sleep_hours", "rem_sleep_hours", "sleep_hours"),
    "pct_deep": ("deep_sleep_hours", "sleep_hours"),
    "pct_rem": ("rem_sleep_hours", "sleep_hours"),
    "high_intensity_min": ("hr_zone_4_min", "hr_zone_5_min"),
    "consecutive_training_days": ("workout_completed",),
}


def resolve_primitives(column: str) -> set[str]:
    """Reduce a feature name to the raw panel columns behind it.

    Lag and z-score suffixes are stripped first, so `day_strain_lag1` and `acwr` both
    resolve to `day_strain`.
    """
    base = column
    for suffix in ("_lag1", "_lag2", "_lag3", "_prev"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    return set(FEATURE_PROVENANCE.get(base, (base,)))


def circularity_report(result: CNSResult, exposure: str) -> dict:
    """Does `exposure` feed into the score we are about to test it against?

    Call this before claiming a score "responds to" something. If the exposure is one
    of the score's own ingredients, the association is guaranteed by construction and
    the honest comparison is against the components that do *not* consume it.
    """
    target = resolve_primitives(exposure)
    implicated = []
    for c in result.components:
        consumed: set[str] = set()
        for i in c.inputs:
            consumed |= resolve_primitives(i)
        if consumed & target:
            implicated.append(
                {"component": c.name, "label": c.label, "weight": c.weight, "via": sorted(consumed & target)}
            )

    contaminated_weight = sum(c["weight"] for c in implicated)
    return {
        "exposure": exposure,
        "resolves_to": sorted(target),
        "circular": bool(implicated),
        "implicated_components": implicated,
        "contaminated_weight": round(contaminated_weight, 3),
        "clean_weight": round(1.0 - contaminated_weight, 3),
        "interpretation": (
            f"{contaminated_weight:.0%} of this score is built from '{exposure}'. Any "
            f"association between the two is partly construction, not evidence. Compare "
            f"using the remaining {1 - contaminated_weight:.0%} of the score, or pick an "
            f"exposure the score does not consume."
            if implicated
            else f"'{exposure}' is not an input to this score; the comparison is clean."
        ),
    }
