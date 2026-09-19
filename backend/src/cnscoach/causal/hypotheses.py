"""The pre-registered hypothesis family.

Every question the engine will ever ask is declared here, *before* looking at results,
together with its expected direction and its region of practical equivalence. This is
the structural defence against p-hacking: the engine cannot go fishing, because the
family is fixed and the multiplicity correction is applied across all of it.

Adding a hypothesis is a deliberate act that widens the correction for everything else.
That is the intended incentive.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Direction = Literal["negative", "positive", "either"]


@dataclass(frozen=True)
class Hypothesis:
    """One pre-registered question."""

    id: str
    family: str
    question: str
    outcome: str
    exposure: str
    covariates: tuple[str, ...] = ()
    direction: Direction = "either"

    #: Smallest effect worth caring about, as a fraction of the outcome's within-athlete
    #: SD per 1 SD of exposure. Effects bounded inside this are reported as negligible.
    rope_sd_frac: float = 0.05

    #: Plain-language template. `{effect}`, `{ci}`, `{n}` are filled by the engine.
    plain_template: str = ""

    #: Supporting literature (PMIDs). These justify *asking*; they never substitute for
    #: the athlete's own data, and the coach must say so.
    pmids: tuple[str, ...] = ()

    #: Bins for the dose-response check, in exposure units.
    dose_bins: tuple[float, ...] | None = None

    #: Why this might be confounded. Surfaced verbatim to the user alongside the result.
    confounding_note: str = ""

    tags: tuple[str, ...] = field(default_factory=tuple)

    @property
    def expected_sign(self) -> int | None:
        return {"negative": -1, "positive": 1, "either": None}[self.direction]


# Covariate sets reused across hypotheses. Day-of-week absorbs the training-week
# structure; day_index absorbs any monotone drift over the study period.
TEMPORAL = ("day_index", "is_weekend")


HYPOTHESES: tuple[Hypothesis, ...] = (
    # ---------------------------------------------------------------- A: load -> autonomic
    Hypothesis(
        id="A1_strain_to_hrv",
        family="Training load to autonomic response",
        question="Does yesterday's cardiovascular load suppress this morning's HRV?",
        outcome="hrv",
        exposure="day_strain_lag1",
        covariates=("day_strain_lag2", "sleep_hours_lag1", *TEMPORAL),
        direction="negative",
        rope_sd_frac=0.03,
        plain_template=(
            "Each extra point of strain yesterday is followed by {effect} in this "
            "morning's HRV ({ci}), across {n} athlete-days."
        ),
        pmids=("37754967", "31642195", "33202732"),
        dose_bins=(0, 5, 8, 11, 14, 17, 21),
        confounding_note=(
            "Observational. High-strain days are chosen, not assigned — an athlete who "
            "feels good trains harder, which biases this toward zero if anything."
        ),
        tags=("load", "hrv", "core"),
    ),
    Hypothesis(
        id="A2_strain_to_rhr",
        family="Training load to autonomic response",
        question="Does yesterday's load elevate this morning's resting heart rate?",
        outcome="resting_heart_rate",
        exposure="day_strain_lag1",
        covariates=("day_strain_lag2", "sleep_hours_lag1", *TEMPORAL),
        direction="positive",
        rope_sd_frac=0.03,
        plain_template=(
            "Each extra point of strain yesterday is followed by {effect} in resting "
            "heart rate ({ci}), across {n} athlete-days."
        ),
        pmids=("37754967", "31642195"),
        dose_bins=(0, 5, 8, 11, 14, 17, 21),
        confounding_note="Observational; same self-selection caveat as A1.",
        tags=("load", "rhr", "core"),
    ),
    Hypothesis(
        id="A3_intensity_to_hrv",
        family="Training load to autonomic response",
        question="Do high-intensity minutes cost more HRV than total load alone?",
        outcome="hrv",
        exposure="high_intensity_min_lag1",
        covariates=("day_strain_lag1", *TEMPORAL),
        direction="negative",
        plain_template=(
            "Holding total strain constant, each extra minute in zones 4-5 yesterday is "
            "followed by {effect} in HRV ({ci})."
        ),
        pmids=("31642195", "37754967"),
        confounding_note=(
            "Conditioning on total strain means this estimates the *composition* effect. "
            "Strain and intensity minutes are strongly correlated, so the two coefficients "
            "are hard to separate cleanly."
        ),
        tags=("load", "intensity"),
    ),
    Hypothesis(
        id="A4_acwr_to_hrv",
        family="Training load to autonomic response",
        question="Does a spike in acute relative to chronic load suppress HRV?",
        outcome="hrv",
        exposure="acwr",
        covariates=("load_chronic", *TEMPORAL),
        direction="negative",
        plain_template="A 1-unit rise in acute:chronic load ratio accompanies {effect} in HRV ({ci}).",
        pmids=("35344471", "33202732"),
        dose_bins=(0, 0.8, 1.0, 1.3, 1.5, 2.0, 5.0),
        confounding_note=(
            "ACWR is a ratio of two smoothed series and is mathematically coupled to its "
            "own denominator; chronic load is included as a covariate to blunt this."
        ),
        tags=("load", "acwr"),
    ),
    Hypothesis(
        id="A5_rebound",
        family="Training load to autonomic response",
        question="Is there a parasympathetic rebound two days after a hard session?",
        outcome="hrv",
        exposure="day_strain_lag2",
        covariates=("day_strain_lag1", "day_strain_lag3", *TEMPORAL),
        direction="positive",
        plain_template=(
            "Two days after a hard session, HRV moves by {effect} per strain point ({ci}) "
            "— the signature of parasympathetic rebound, once the day-1 dip is held constant."
        ),
        pmids=("31642195", "35344471"),
        confounding_note=(
            "Strain is autocorrelated across days, so lag-1 and lag-2 coefficients are "
            "partially entangled even with both in the model."
        ),
        tags=("load", "hrv", "rebound"),
    ),
    # ---------------------------------------------------------------- B: sleep -> next day
    Hypothesis(
        id="B1_sleep_to_hrv",
        family="Sleep to next-day state",
        question="Does a longer night raise the next morning's HRV?",
        outcome="hrv",
        exposure="sleep_hours_lag1",
        covariates=("day_strain_lag1", "sleep_efficiency_lag1", *TEMPORAL),
        direction="positive",
        plain_template="Each extra hour of sleep is followed by {effect} in HRV ({ci}).",
        pmids=("35409591",),
        dose_bins=(4, 6, 6.5, 7, 7.5, 8, 10),
        confounding_note="Observational; illness and stress move sleep and HRV together.",
        tags=("sleep", "hrv", "core"),
    ),
    Hypothesis(
        id="B2_sleep_to_recovery",
        family="Sleep to next-day state",
        question="Does a longer night raise the next day's recovery score?",
        outcome="recovery_score",
        exposure="sleep_hours_lag1",
        covariates=("day_strain_lag1", "sleep_efficiency_lag1", *TEMPORAL),
        direction="positive",
        plain_template="Each extra hour of sleep is followed by {effect} in recovery score ({ci}).",
        pmids=("35409591",),
        dose_bins=(4, 6, 6.5, 7, 7.5, 8, 10),
        confounding_note="Observational.",
        tags=("sleep", "recovery", "core", "score_audit"),
    ),
    Hypothesis(
        id="B3_sleep_debt_to_recovery",
        family="Sleep to next-day state",
        question="Does accumulated 7-day sleep debt depress recovery?",
        outcome="recovery_score",
        exposure="sleep_debt_7d",
        covariates=("day_strain_lag1", *TEMPORAL),
        direction="negative",
        plain_template="Each hour of accumulated 7-day sleep debt accompanies {effect} in recovery ({ci}).",
        pmids=("35409591",),
        confounding_note="Debt is measured against the athlete's own trailing median need.",
        tags=("sleep", "recovery"),
    ),
    Hypothesis(
        id="B4_fragmentation_to_hrv",
        family="Sleep to next-day state",
        question="Does a fragmented night cost HRV independently of duration?",
        outcome="hrv",
        exposure="wake_ups_lag1",
        covariates=("sleep_hours_lag1", "day_strain_lag1", *TEMPORAL),
        direction="negative",
        plain_template="Each additional awakening is followed by {effect} in HRV ({ci}).",
        pmids=("35409591",),
        confounding_note="Wake-ups are zero on more than half of nights, limiting resolution.",
        tags=("sleep", "hrv"),
    ),
    Hypothesis(
        id="B5_irregularity_to_recovery",
        family="Sleep to next-day state",
        question="Does an irregular sleep schedule depress recovery?",
        outcome="recovery_score",
        exposure="sleep_irregularity",
        covariates=("sleep_hours_lag1", "day_strain_lag1", *TEMPORAL),
        direction="negative",
        plain_template="Each extra hour of SD in sleep duration accompanies {effect} in recovery ({ci}).",
        pmids=("35409591",),
        confounding_note=(
            "Irregularity is a trailing-window statistic, so it changes slowly and is "
            "partly a property of the athlete rather than the day."
        ),
        tags=("sleep", "recovery", "circadian"),
    ),
    # ---------------------------------------------------------------- C: auditing the score
    Hypothesis(
        id="C1_strain_to_recovery",
        family="Auditing the composite score",
        question=(
            "Does yesterday's load move the recovery score the way it moves the raw "
            "physiology it is supposedly built from?"
        ),
        outcome="recovery_score",
        exposure="day_strain_lag1",
        covariates=("day_strain_lag2", "sleep_hours_lag1", *TEMPORAL),
        direction="negative",
        rope_sd_frac=0.03,
        plain_template=(
            "Each extra point of strain yesterday moves the recovery score by {effect} "
            "({ci}) — compare this against the same exposure's effect on raw HRV (A1)."
        ),
        pmids=("37754967", "31642195"),
        dose_bins=(0, 5, 8, 11, 14, 17, 21),
        confounding_note=(
            "This hypothesis exists to compare a proprietary composite against its own "
            "inputs. A null here alongside a clear effect in A1 means the composite is "
            "discarding load information that its raw signals contain."
        ),
        tags=("recovery", "score_audit", "core"),
    ),
    Hypothesis(
        id="C2_hrv_to_recovery",
        family="Auditing the composite score",
        question="How much of the recovery score is just today's HRV?",
        outcome="recovery_score",
        exposure="hrv",
        covariates=("resting_heart_rate", *TEMPORAL),
        direction="positive",
        plain_template="The recovery score moves by {effect} ({ci}).",
        pmids=("30300066",),
        confounding_note=(
            "Same-day, not lagged: this is a decomposition of the score, not a causal "
            "claim. It quantifies how much of the black box is recoverable from two inputs."
        ),
        tags=("recovery", "score_audit", "same_day"),
    ),
    # ---------------------------------------------------------------- D: compound exposures
    Hypothesis(
        id="D1_double_hit",
        family="Compound exposures",
        question="Do short sleep and high strain together cost more than either alone?",
        outcome="hrv",
        exposure="double_hit_prev",
        covariates=("short_sleep_prev", "high_strain_prev", *TEMPORAL),
        direction="negative",
        plain_template=(
            "Nights that combine short sleep with a hard day are followed by {effect} in "
            "HRV ({ci}) *beyond* the sum of the two separately."
        ),
        pmids=("35409591", "35344471"),
        confounding_note=(
            "This is an interaction term with both main effects held in the model, so it "
            "estimates super-additivity only. Exposed days are a small subset."
        ),
        tags=("compound", "interaction", "core"),
    ),
    Hypothesis(
        id="D2_consecutive_days",
        family="Compound exposures",
        question="Does HRV decline across a block of consecutive training days?",
        outcome="hrv",
        exposure="consecutive_training_days",
        covariates=("day_strain_lag1", *TEMPORAL),
        direction="negative",
        plain_template="Each additional consecutive training day accompanies {effect} in HRV ({ci}).",
        pmids=("33202732", "35344471"),
        dose_bins=(0, 1, 2, 3, 5, 7, 30),
        confounding_note="Long blocks are more common in athletes who tolerate them (survivorship).",
        tags=("load", "accumulation"),
    ),
    Hypothesis(
        id="D3_monotony",
        family="Compound exposures",
        question="Does monotonous training (little day-to-day variation) suppress HRV?",
        outcome="hrv",
        exposure="monotony",
        covariates=("load_acute", *TEMPORAL),
        direction="negative",
        plain_template="Each 1-unit rise in Foster monotony accompanies {effect} in HRV ({ci}).",
        pmids=("35344471",),
        confounding_note="Monotony is undefined on weeks with zero load variance.",
        tags=("load", "monotony"),
    ),
    # ---------------------------------------------------------------- E: systemic stress
    Hypothesis(
        id="E1_resp_rate_to_recovery",
        family="Systemic stress signals",
        question="Does an elevated respiratory rate precede a drop in recovery?",
        outcome="recovery_score",
        exposure="respiratory_rate_z",
        covariates=("day_strain_lag1", "sleep_hours_lag1", *TEMPORAL),
        direction="negative",
        plain_template="Each SD of elevated respiratory rate accompanies {effect} in recovery ({ci}).",
        pmids=("35409591",),
        confounding_note="Respiratory rate rises with illness, altitude and alcohol alike.",
        tags=("illness", "recovery"),
    ),
    Hypothesis(
        id="E2_skin_temp_to_hrv",
        family="Systemic stress signals",
        question="Does a skin-temperature excursion accompany suppressed HRV?",
        outcome="hrv",
        exposure="skin_temp_deviation",
        covariates=("day_strain_lag1", *TEMPORAL),
        direction="either",
        plain_template="Each 1 °C of skin-temperature deviation accompanies {effect} in HRV ({ci}).",
        pmids=("35409591",),
        confounding_note=(
            "Direction is not pre-specified: both fever and a cold room move this, in "
            "opposite directions."
        ),
        tags=("illness", "hrv"),
    ),
)


HYPOTHESES_BY_ID: dict[str, Hypothesis] = {h.id: h for h in HYPOTHESES}


def get(hypothesis_id: str) -> Hypothesis:
    if hypothesis_id not in HYPOTHESES_BY_ID:
        raise KeyError(f"Unknown hypothesis '{hypothesis_id}'. Known: {sorted(HYPOTHESES_BY_ID)}")
    return HYPOTHESES_BY_ID[hypothesis_id]


def by_tag(tag: str) -> list[Hypothesis]:
    return [h for h in HYPOTHESES if tag in h.tags]


def families() -> list[str]:
    seen: list[str] = []
    for h in HYPOTHESES:
        if h.family not in seen:
            seen.append(h.family)
    return seen


def all_pmids() -> list[str]:
    out: list[str] = []
    for h in HYPOTHESES:
        for p in h.pmids:
            if p not in out:
                out.append(p)
    return out
