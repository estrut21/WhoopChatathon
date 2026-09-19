"""Tests for the statistical core.

These target the properties the whole project rests on: that fixed effects actually
absorb between-athlete variation, that clustered SEs are not anticonservative, and that
the multiplicity and equivalence machinery does what it claims.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from cnscoach.causal import estimators as est
from cnscoach.causal.validation import PlantedEffect, synthesize_panel
from cnscoach.data.schema import ATHLETE_ID


@pytest.fixture(scope="module")
def planted():
    return synthesize_panel(
        n_athletes=60,
        n_days=120,
        effects=[PlantedEffect("day_strain", "hrv", coef=-1.0)],
        seed=7,
    )


def test_recovers_planted_effect(planted):
    e = est.within_athlete_fe(planted, "hrv", ["day_strain_lag1"]).get("day_strain_lag1")
    assert e.ci_low <= -1.0 <= e.ci_high
    assert e.coef == pytest.approx(-1.0, abs=0.1)


def test_fixed_effects_absorb_between_athlete_confounding():
    """A pure between-athlete association must not survive the within transform.

    Athletes are given HRV and strain levels that are correlated across people but
    unrelated within any individual. A pooled regression finds a strong effect; the
    within-athlete estimator should find nothing.
    """
    rng = np.random.default_rng(3)
    rows = []
    for a in range(80):
        level = rng.normal(0, 1)
        for d in range(60):
            rows.append(
                {
                    ATHLETE_ID: f"A{a}",
                    "day_strain_lag1": 10 + 5 * level + rng.normal(0, 1),
                    "hrv": 70 + 20 * level + rng.normal(0, 5),
                }
            )
    df = pd.DataFrame(rows)

    pooled = np.corrcoef(df.day_strain_lag1, df.hrv)[0, 1]
    assert abs(pooled) > 0.5, "fixture should have strong between-athlete confounding"

    e = est.within_athlete_fe(df, "hrv", ["day_strain_lag1"]).get("day_strain_lag1")
    assert e.ci_low <= 0 <= e.ci_high, "within-athlete estimate should not detect an effect"


def test_clustered_se_exceeds_naive_se(planted):
    """Ignoring clustering understates uncertainty; that is the whole reason for it."""
    e = est.within_athlete_fe(planted, "hrv", ["day_strain_lag1"]).get("day_strain_lag1")

    d = planted.dropna(subset=["hrv", "day_strain_lag1"])
    y = d.hrv - d.groupby(ATHLETE_ID).hrv.transform("mean")
    x = d.day_strain_lag1 - d.groupby(ATHLETE_ID).day_strain_lag1.transform("mean")
    resid = y - x * (x @ y) / (x @ x)
    naive_se = np.sqrt((resid**2).sum() / (len(d) - 2) / (x**2).sum())

    assert e.se >= naive_se * 0.95


def test_holm_controls_family_wise_error():
    p = [0.001, 0.01, 0.03, 0.04, 0.2]
    adj = est.holm_bonferroni(p)
    assert adj[0] == pytest.approx(0.005)
    assert all(adj[i] <= adj[i + 1] for i in range(len(adj) - 1)), "must be monotone"
    assert all(a >= b for a, b in zip(adj, p)), "adjusted p never below raw p"
    assert np.all(adj <= 1.0)


def test_holm_handles_edge_cases():
    assert len(est.holm_bonferroni([])) == 0
    assert est.holm_bonferroni([0.5])[0] == pytest.approx(0.5)
    assert np.all(est.holm_bonferroni([0.9, 0.95]) <= 1.0)


def test_tost_detects_equivalence_for_tiny_effect():
    e = est.Estimate(
        term="x", coef=0.001, se=0.0005, t_stat=2.0, p_value=0.05,
        ci_low=0.0, ci_high=0.002, df=100, n_obs=1000, n_clusters=101,
    )
    assert est.tost_equivalence(e, rope=0.5) < 0.05, "a tiny effect vs a wide ROPE is equivalent"
    assert est.tost_equivalence(e, rope=0.0005) > 0.05, "a narrow ROPE should not pass"


def test_tost_rejects_non_positive_rope():
    e = est.Estimate("x", 0.1, 0.05, 2.0, 0.05, 0.0, 0.2, 100, 1000, 101)
    with pytest.raises(ValueError):
        est.tost_equivalence(e, rope=0.0)


def test_negative_control_kills_a_shuffled_exposure(planted):
    nc = est.permutation_negative_control(
        planted, "hrv", "day_strain_lag1", n_permutations=40, seed=1
    )
    assert nc["passes"], "a genuinely planted effect should beat its own null distribution"
    assert abs(nc["null_mean"]) < abs(nc["observed_coef"]) / 3


def test_min_obs_filter_drops_thin_athletes():
    rng = np.random.default_rng(11)
    rows = []
    for a in range(20):
        n = 50 if a < 15 else 5  # five athletes are too thin to use
        for d in range(n):
            rows.append(
                {ATHLETE_ID: f"A{a}", "y": rng.normal(), "x": rng.normal()}
            )
    df = pd.DataFrame(rows)
    fit = est.within_athlete_fe(df, "y", ["x"], min_obs_per_athlete=30)
    assert fit.n_clusters == 15
    assert any("dropped" in w for w in fit.warnings)


def test_raises_on_missing_columns(planted):
    with pytest.raises(KeyError):
        est.within_athlete_fe(planted, "hrv", ["not_a_column"])


def test_raises_when_no_within_variance():
    df = pd.DataFrame(
        {ATHLETE_ID: ["A"] * 40 + ["B"] * 40, "y": np.arange(80.0), "x": [1.0] * 40 + [2.0] * 40}
    )
    # x varies between athletes but is constant within each, so nothing is identified.
    with pytest.raises(ValueError):
        est.within_athlete_fe(df, "y", ["x"], min_obs_per_athlete=10)


def test_dose_response_is_monotonic_for_a_linear_effect(planted):
    dr = est.dose_response(planted, "hrv", "day_strain_lag1", bins=[0, 6, 9, 12, 15, 25])
    assert len(dr) == 5
    assert dr.attrs["monotonic"], "a linear planted effect should give a monotone curve"


def test_cluster_bootstrap_agrees_with_sandwich(planted):
    boot = est.cluster_bootstrap_ci(
        planted, "hrv", "day_strain_lag1", n_draws=60, seed=5
    )
    e = est.within_athlete_fe(planted, "hrv", ["day_strain_lag1"]).get("day_strain_lag1")
    # Two independent routes to the same uncertainty should broadly agree.
    assert boot["ci_low"] <= e.coef <= boot["ci_high"]
    assert boot["boot_se"] == pytest.approx(e.se, rel=0.5)
