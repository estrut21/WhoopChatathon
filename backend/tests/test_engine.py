"""Tests for verdict classification and the data layer.

The verdict logic is where statistical significance and practical importance are kept
apart, so each cell of that cross is tested explicitly.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from cnscoach.causal.engine import Verdict, _classify, run_hypothesis
from cnscoach.causal.hypotheses import HYPOTHESES, Hypothesis, get
from cnscoach.causal.validation import PlantedEffect, synthesize_panel
from cnscoach.data.schema import ATHLETE_ID, DATE


class _Probe:
    """Minimal stand-in carrying just the fields `_classify` reads."""

    def __init__(self, coef: float, p_adjusted: float, equivalence_p: float):
        self.coef = coef
        self.p_adjusted = p_adjusted
        self.equivalence_p = equivalence_p


H_NEG = Hypothesis(
    id="t", family="t", question="?", outcome="hrv", exposure="x", direction="negative"
)


def test_supported_requires_significance_and_relevance():
    # Detectable, and not bounded inside the ROPE.
    v = _classify(_Probe(coef=-1.0, p_adjusted=0.001, equivalence_p=0.9), H_NEG)
    assert v is Verdict.SUPPORTED


def test_detectable_but_trivial_when_significant_and_bounded():
    """The cell most products collapse into a headline. It must stay distinct."""
    v = _classify(_Probe(coef=-0.01, p_adjusted=1e-9, equivalence_p=0.001), H_NEG)
    assert v is Verdict.DETECTABLE_BUT_TRIVIAL


def test_negligible_when_neither_significant_nor_relevant():
    v = _classify(_Probe(coef=-0.001, p_adjusted=0.8, equivalence_p=0.001), H_NEG)
    assert v is Verdict.NEGLIGIBLE


def test_inconclusive_when_neither_rejected_nor_bounded():
    """Underpowered must never be reported as a null."""
    v = _classify(_Probe(coef=-0.5, p_adjusted=0.4, equivalence_p=0.7), H_NEG)
    assert v is Verdict.INCONCLUSIVE


def test_direction_reversed_is_surfaced_not_dropped():
    v = _classify(_Probe(coef=+1.0, p_adjusted=0.001, equivalence_p=0.9), H_NEG)
    assert v is Verdict.DIRECTION_REVERSED


def test_direction_agnostic_hypothesis_never_reverses():
    h = Hypothesis(id="t", family="t", question="?", outcome="hrv", exposure="x", direction="either")
    assert _classify(_Probe(1.0, 0.001, 0.9), h) is Verdict.SUPPORTED
    assert _classify(_Probe(-1.0, 0.001, 0.9), h) is Verdict.SUPPORTED


# ---------------------------------------------------------------- hypothesis registry


def test_hypothesis_ids_are_unique():
    ids = [h.id for h in HYPOTHESES]
    assert len(ids) == len(set(ids))


def test_every_hypothesis_declares_its_caveats():
    for h in HYPOTHESES:
        assert h.confounding_note, f"{h.id} must state how it could be confounded"
        assert 0 < h.rope_sd_frac < 1, f"{h.id} has an implausible ROPE"
        assert h.family


def test_get_rejects_unknown_hypothesis():
    with pytest.raises(KeyError):
        get("nope")


# ---------------------------------------------------------------- end-to-end on planted data


@pytest.fixture(scope="module")
def planted_features():
    panel = synthesize_panel(
        n_athletes=60,
        n_days=120,
        effects=[PlantedEffect("day_strain", "hrv", coef=-1.0)],
        seed=17,
    )
    panel["day_index"] = panel.groupby(ATHLETE_ID).cumcount()
    panel["is_weekend"] = panel[DATE].dt.dayofweek.isin([5, 6]).astype(int)
    panel["day_strain_lag2"] = panel.groupby(ATHLETE_ID)["day_strain"].shift(2)
    panel["day_strain_lag3"] = panel.groupby(ATHLETE_ID)["day_strain"].shift(3)
    return panel


def test_run_hypothesis_finds_a_large_planted_effect(planted_features):
    f = run_hypothesis(planted_features, get("A1_strain_to_hrv"), with_dose_response=True)
    assert f is not None
    f.p_adjusted = f.p_value
    from cnscoach.causal.engine import _classify as classify

    assert classify(f, get("A1_strain_to_hrv")) is Verdict.SUPPORTED
    assert f.ci_low <= -1.0 <= f.ci_high


def test_run_hypothesis_returns_none_when_columns_are_absent():
    empty = pd.DataFrame({ATHLETE_ID: ["A"] * 5, "hrv": [1.0] * 5})
    assert run_hypothesis(empty, get("A1_strain_to_hrv")) is None


def test_realistic_swing_is_a_within_athlete_range(planted_features):
    f = run_hypothesis(planted_features, get("A1_strain_to_hrv"), with_dose_response=False)
    assert f is not None
    # Strain has SD ~4, so a within-athlete p10-p90 spread should be roughly 10 units,
    # and must not be inflated by between-athlete differences.
    assert 5 < f.realistic_swing < 20


# ---------------------------------------------------------------- feature engineering


def test_rolling_features_never_peek_at_the_future():
    """A feature for day t must be computable on the morning of day t."""
    from cnscoach.data.features import build_features

    rng = np.random.default_rng(5)
    df = pd.DataFrame(
        {
            ATHLETE_ID: ["A"] * 80,
            DATE: pd.date_range("2024-01-01", periods=80),
            "hrv": rng.normal(70, 10, 80),
            "resting_heart_rate": rng.normal(55, 4, 80),
            "respiratory_rate": rng.normal(15, 1, 80),
            "skin_temp_deviation": rng.normal(0, 0.3, 80),
            "day_strain": rng.uniform(0, 20, 80),
            "sleep_hours": rng.normal(7.3, 0.8, 80),
            "sleep_efficiency": rng.normal(85, 5, 80),
            "deep_sleep_hours": [1.3] * 80,
            "rem_sleep_hours": [1.6] * 80,
            "light_sleep_hours": [4.4] * 80,
            "wake_ups": rng.poisson(0.4, 80),
            "workout_completed": (rng.random(80) > 0.5).astype(int),
        }
    )
    base = build_features(df)

    # Perturbing the final day must not change any earlier row's features.
    perturbed = df.copy()
    perturbed.loc[perturbed.index[-1], "day_strain"] = 21.0
    perturbed.loc[perturbed.index[-1], "hrv"] = 5.0
    after = build_features(perturbed)

    for col in ("load_acute", "load_chronic", "acwr", "sleep_debt_7d", "ln_hrv_baseline"):
        pd.testing.assert_series_equal(
            base[col].iloc[:-1], after[col].iloc[:-1], check_names=False
        )


def test_baselines_are_personal_not_population():
    """Two athletes with very different HRV levels should both sit near z=0."""
    from cnscoach.data.features import build_features

    rng = np.random.default_rng(9)
    rows = []
    for aid, level in (("LOW", 35.0), ("HIGH", 120.0)):
        for d in range(90):
            rows.append(
                {
                    ATHLETE_ID: aid,
                    DATE: pd.Timestamp("2024-01-01") + pd.Timedelta(days=d),
                    "hrv": level + rng.normal(0, level * 0.1),
                    "resting_heart_rate": 55 + rng.normal(0, 4),
                    "respiratory_rate": 15.0,
                    "skin_temp_deviation": 0.0,
                    "day_strain": rng.uniform(0, 20),
                    "sleep_hours": 7.3,
                    "sleep_efficiency": 85.0,
                    "deep_sleep_hours": 1.3,
                    "rem_sleep_hours": 1.6,
                    "light_sleep_hours": 4.4,
                    "wake_ups": 0,
                    "workout_completed": 1,
                }
            )
    feats = build_features(pd.DataFrame(rows))
    tail = feats.groupby(ATHLETE_ID).tail(30)
    means = tail.groupby(ATHLETE_ID)["ln_hrv_z"].mean()
    assert abs(means["LOW"]) < 0.6 and abs(means["HIGH"]) < 0.6
