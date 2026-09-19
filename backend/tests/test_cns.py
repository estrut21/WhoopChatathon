"""Tests for the CNS score contract.

The contract is about explainability, so that is what is tested: components must
reconcile to the score, weights must sum to one, missing inputs must be declared rather
than silently dropped, and an immature baseline must produce a refusal to score.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from cnscoach.cns import available, get_model, score_athlete_series, score_day
from cnscoach.cns import base as B
from cnscoach.cns.registry import names
from cnscoach.data.schema import ATHLETE_ID, DATE


@pytest.fixture(scope="module")
def features():
    """A small synthetic panel carrying the columns the scorers expect."""
    rng = np.random.default_rng(42)
    rows = []
    for a in range(3):
        for d in range(120):
            rows.append(
                {
                    ATHLETE_ID: f"T{a}",
                    DATE: pd.Timestamp("2024-01-01") + pd.Timedelta(days=d),
                    "hrv": 70 + rng.normal(0, 10),
                    "resting_heart_rate": 55 + rng.normal(0, 4),
                    "respiratory_rate": 15 + rng.normal(0, 1),
                    "skin_temp_deviation": rng.normal(0, 0.4),
                    "day_strain": np.clip(rng.normal(10, 4), 0, 21),
                    "sleep_hours": np.clip(rng.normal(7.3, 0.9), 4, 10),
                    "sleep_efficiency": np.clip(rng.normal(85, 8), 50, 100),
                    "deep_sleep_hours": 1.3,
                    "rem_sleep_hours": 1.6,
                    "light_sleep_hours": 4.4,
                    "wake_ups": rng.poisson(0.4),
                    "workout_completed": int(rng.random() > 0.45),
                    "hr_zone_4_min": rng.uniform(0, 20),
                    "hr_zone_5_min": rng.uniform(0, 8),
                }
            )
    from cnscoach.data.features import build_features

    return build_features(pd.DataFrame(rows))


@pytest.mark.parametrize("model_name", sorted(names()))
def test_components_reconcile_to_score(features, model_name):
    result = score_day(features, "T0", features.date.max(), model_name=model_name)
    total = sum(c.contribution for c in result.components)
    assert total == pytest.approx(result.score, abs=0.51)
    result.validate()  # raises if the invariant is broken


@pytest.mark.parametrize("model_name", sorted(names()))
def test_weights_sum_to_one(model_name):
    weights = getattr(get_model(model_name), "weights", {})
    assert sum(weights.values()) == pytest.approx(1.0)


@pytest.mark.parametrize("model_name", sorted(names()))
def test_score_is_bounded(features, model_name):
    series = score_athlete_series(features, "T0", model_name=model_name)
    scored = series[~series.calibrating]
    assert not scored.empty
    assert scored.cns_score.between(0, 100).all()


def test_refuses_to_score_an_immature_baseline(features):
    early = features[features[ATHLETE_ID] == "T0"].sort_values(DATE).date.iloc[3]
    result = score_day(features, "T0", early)
    assert result.calibrating
    assert "calibrating" in result.explain().lower()
    assert str(B.MIN_BASELINE_DAYS) in result.explain()


def test_missing_inputs_are_declared_not_hidden(features):
    """A component whose input is absent must be flagged and held at neutral."""
    damaged = features.copy()
    damaged["respiratory_rate_z"] = np.nan
    damaged["skin_temp_deviation"] = np.nan

    result = score_day(damaged, "T0", damaged.date.max())
    systemic = next(c for c in result.components if c.name == "systemic_stress")
    assert not systemic.available
    assert systemic.subscore == pytest.approx(50.0)
    assert result.data_completeness < 1.0
    assert any("missing" in c.lower() for c in result.caveats)


def test_every_component_declares_its_inputs(features):
    result = score_day(features, "T0", features.date.max())
    for c in result.components:
        assert c.inputs, f"{c.name} must declare inputs for the circularity check"


def test_circularity_is_detected_for_an_ingredient(features):
    result = score_day(features, "T0", features.date.max())
    rep = B.circularity_report(result, "day_strain_lag1")
    assert rep["circular"]
    assert rep["contaminated_weight"] > 0
    assert any(c["component"] == "load_balance" for c in rep["implicated_components"])


def test_circularity_is_clean_for_a_non_ingredient(features):
    result = score_day(features, "T0", features.date.max())
    rep = B.circularity_report(result, "wake_ups_lag1")
    assert not rep["circular"]
    assert rep["contaminated_weight"] == 0


def test_resolve_primitives_strips_lags_and_derivations():
    assert B.resolve_primitives("day_strain_lag1") == {"day_strain"}
    assert B.resolve_primitives("acwr") == {"day_strain"}
    assert B.resolve_primitives("ln_hrv_z") == {"hrv"}
    assert B.resolve_primitives("wake_ups") == {"wake_ups"}


def test_z_to_subscore_saturates_symmetrically():
    assert B.z_to_subscore(0.0) == pytest.approx(50.0)
    assert B.z_to_subscore(10.0) == 100.0
    assert B.z_to_subscore(-10.0) == 0.0
    assert B.z_to_subscore(float("nan")) == 50.0
    assert B.z_to_subscore(1.0, higher_is_better=False) < 50.0


def test_u_shaped_subscore_penalises_both_directions():
    assert B.u_shaped_subscore(1.0, optimal=1.0, tolerance=0.3) == 100.0
    low = B.u_shaped_subscore(0.4, optimal=1.0, tolerance=0.3)
    high = B.u_shaped_subscore(1.6, optimal=1.0, tolerance=0.3)
    assert low < 100 and high < 100
    assert low == pytest.approx(high), "symmetric deviation should cost the same"


def test_registry_lists_models_and_rejects_unknown():
    assert {"v0_autonomic", "v1_template"} <= set(names())
    assert all("description" in m for m in available())
    with pytest.raises(KeyError):
        get_model("not_a_model")


def test_components_coerce_numpy_scalars_to_native_types():
    """Regression: np.bool_ from np.isfinite() broke JSON serialisation at the API."""
    c = B.Component(
        name="x",
        label="X",
        raw_value=np.float64(1.5),
        subscore=np.float64(50.0),
        weight=np.float64(0.5),
        contribution=np.float64(25.0),
        available=np.isfinite(np.float64(1.0)),
    )
    assert type(c.available) is bool
    assert type(c.subscore) is float
    import json

    json.dumps(c.to_dict())  # must not raise


def test_scored_result_is_json_serialisable(features):
    import json

    json.dumps(score_day(features, "T0").to_dict())


def test_invalid_result_is_rejected():
    bad = B.CNSResult(
        score=80.0,
        band="Primed",
        components=[B.Component("a", "A", 1.0, 100.0, 1.0, 12.0)],  # 100*1.0 != 80
        model_name="broken",
        model_version="0",
        confidence=1.0,
        data_completeness=1.0,
        baseline_days_available=100,
        calibrating=False,
    )
    with pytest.raises(ValueError, match="decompos"):
        bad.validate()
