"""Tests for citation enforcement.

The hallucination cases here are the actual product claim, so they are written as
adversarially as possible: a fabricated number surrounded by real ones, a number that
is arithmetically derivable from unrelated facts, and a number just outside the
rounding tolerance it was written to.
"""

from __future__ import annotations

import pytest

from cnscoach.coach import guardrails as G


@pytest.fixture
def ledger():
    led = G.FactLedger()
    led.add_mapping(
        {
            "coef": -0.05339880519895325,
            "ci_low": -0.0727604,
            "ci_high": -0.0340372,
            "p_adjusted": 1.9463738185522704e-06,
            "n_obs": 99428,
            "pct_of_outcome_sd": -1.7368466756042693,
        },
        source="get_finding(A1)",
    )
    led.add_mapping(
        {"coef": 0.011296811108045066, "p_adjusted": 1.0, "n_obs": 99428},
        source="get_finding(C1)",
    )
    return led


def test_grounded_text_passes(ledger):
    text = (
        "Strain is followed by a fall of 0.0534 ms in HRV "
        "(95% CI -0.0728 to -0.034), Holm p=1.9e-06 across 99428 athlete-days."
    )
    report = G.verify(text, ledger)
    assert report.is_grounded
    assert len(report.verified) == 5


def test_catches_the_classic_fabricated_statistic(ledger):
    text = "Your recovery drops 18% after heavy training and HRV sits 23.7 ms below baseline."
    report = G.verify(text, ledger)
    assert not report.is_grounded
    assert any(v.value == 23.7 for v in report.violations)


def test_catches_a_fabrication_hidden_among_real_numbers(ledger):
    text = (
        "Strain is followed by a fall of 0.0534 ms in HRV (95% CI -0.0728 to -0.034), "
        "which translates to a 41% reduction in training capacity."
    )
    report = G.verify(text, ledger)
    assert not report.is_grounded
    assert [v.value for v in report.violations] == [41.0]


def test_derived_arithmetic_is_off_by_default(ledger):
    """Unrestricted derivation makes nearly any number passable; it must be opt-in."""
    text = "The gap between -0.0534 and 0.0113 is 0.0647."
    assert not G.verify(text, ledger).is_grounded


def test_derived_matching_requires_comparable_fields(ledger):
    """Even enabled, derivation only combines values sharing a field name."""
    # 0.0647 is coef(A1) - coef(C1): both are '.coef', so this is allowed.
    allowed = G.verify("The gap is 0.0647.", ledger, allow_derived=True)
    assert allowed.is_grounded and allowed.derived

    # 23.7 was previously "derivable" as pct_of_outcome_sd / ci_low -- different fields.
    blocked = G.verify("HRV sits 23.7 ms below baseline.", ledger, allow_derived=True)
    assert not blocked.is_grounded


def test_rounding_is_allowed_but_precision_is_held_to(ledger):
    assert G.verify("p was 1.9e-06.", ledger).is_grounded, "2 s.f. rounding is honest"
    assert G.verify("The coefficient is -0.053.", ledger).is_grounded
    # Stating more digits invites a stricter check, and this value is wrong at that precision.
    assert not G.verify("The coefficient is -0.0531.", ledger).is_grounded


def test_rounding_tolerance_tracks_written_precision():
    assert G.rounding_tolerance("23.7") == pytest.approx(0.05)
    assert G.rounding_tolerance("41") == pytest.approx(0.5)
    assert G.rounding_tolerance("0.0534") == pytest.approx(5e-5)
    assert G.rounding_tolerance("1.9e-06") == pytest.approx(5e-8)
    assert G.rounding_tolerance("-1,234.5") == pytest.approx(0.05)


def test_percent_rescaling_only_applies_with_a_percent_sign():
    led = G.FactLedger()
    led.add(0.182, "share", "tool()")
    assert G.verify("That is 18.2% of days.", led).is_grounded
    # The same digits without a % sign must not silently match a proportion.
    assert not G.verify("The value was 18.2 ms.", led).is_grounded


def test_sign_insensitive_matching(ledger):
    """'a fall of 0.0534' is a legitimate rendering of a -0.0534 coefficient."""
    assert G.verify("a fall of 0.0534 ms", ledger).is_grounded


def test_benign_numbers_are_not_flagged(ledger):
    report = G.verify("Over the last 7 days across 3 sessions in 2024.", ledger)
    assert report.is_grounded
    assert report.benign_skipped == 3


def test_confidence_levels_are_not_treated_as_claims(ledger):
    """'95% CI' must not be flagged, or readers learn to ignore the warnings."""
    assert G.verify("The 95% CI runs -0.0728 to -0.034.", ledger).is_grounded


def test_long_integers_are_actually_checked(ledger):
    """Regression: a regex bug made bare integers over three digits invisible."""
    mentions = {m.value for m in G.extract_numbers("n was 99428 and 12345 and 1,234")}
    assert {99428.0, 12345.0, 1234.0} <= mentions

    # And a fabricated large number must therefore be caught.
    assert not G.verify("Based on 87654 athlete-days.", ledger).is_grounded
    assert G.verify("Based on 99428 athlete-days.", ledger).is_grounded


def test_qualitative_text_needs_no_grounding(ledger):
    report = G.verify("Your load is detectable in HRV but not in the recovery score.", ledger)
    assert report.is_grounded
    assert report.n_checked == 0


def test_no_absolute_tolerance_floor_against_zero_facts():
    """A zero-valued fact must not license every small number."""
    led = G.FactLedger()
    led.add(0.0, "hr_zone_5_min", "query()")
    led.add(0.0, "activity_strain", "query()")
    assert not G.verify("HRV fell by 0.004 ms.", led).is_grounded


def test_collision_rate_is_measured_and_plausible(ledger):
    rate = ledger.collision_rate(n_probes=500, seed=1)
    assert 0.0 <= rate < 0.35, "a small ledger should be hard to fool by chance"


def test_collision_rate_grows_with_ledger_size():
    """More retrieved facts means more ways for a wrong number to land near a right one."""
    small, large = G.FactLedger(), G.FactLedger()
    for i in range(5):
        small.add(1.0 + i * 0.37, f"f{i}", "t()")
    for i in range(400):
        large.add(1.0 + i * 0.0037, f"f{i}", "t()")
    assert large.collision_rate(n_probes=400, seed=2) > small.collision_rate(n_probes=400, seed=2)


def test_annotate_marks_only_the_unverified_number(ledger):
    text = "A fall of 0.0534 ms, which is a 41% drop."
    out = G.annotate(text, G.verify(text, ledger))
    assert "[UNVERIFIED: 41]" in out
    assert "0.0534" in out and "UNVERIFIED: 0.0534" not in out


def test_ledger_ignores_booleans_and_nan():
    led = G.FactLedger()
    led.add_mapping({"passes": True, "value": float("nan"), "real": 3.7}, source="t()")
    assert len(led) == 1
