"""Derived features: personal baselines, training-load dynamics, sleep debt, lags.

Two rules hold throughout this module:

1. **Everything is personal.** A baseline is always computed within an athlete, never
   against a population mean. Cross-athlete HRV comparisons are physiologically
   meaningless — a 30 ms athlete is not "unrecovered" relative to a 120 ms athlete.
2. **Nothing peeks at the future.** Every rolling window is shifted by one day, so a
   feature for day *t* is computable from data available on the morning of day *t*.
   This is what makes the lagged regressions in `cnscoach.causal` interpretable as
   "yesterday predicted today" rather than a same-day tautology.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from cnscoach.config import settings
from cnscoach.data.schema import ATHLETE_ID, DATE

# HRV is log-normally distributed; ln-transforming before any averaging or z-scoring is
# standard practice in the training-monitoring literature (see evidence corpus entry
# `hrv_ln_transform`). Untransformed RMSSD means are biased by outlier high days.
LN_HRV = "ln_hrv"


def _shifted_roll(
    g: pd.core.groupby.SeriesGroupBy, window: int, stat: str, min_periods: int
) -> pd.Series:
    """Rolling stat over the *previous* `window` days, excluding today."""
    rolled = g.shift(1).rolling(window=window, min_periods=min_periods)
    return getattr(rolled, stat)()


def add_personal_baselines(df: pd.DataFrame, window: int | None = None) -> pd.DataFrame:
    """Rolling personal baselines and deviations for the autonomic markers.

    Produces, for HRV / RHR / respiratory rate:
      * `<m>_baseline`  — trailing mean over `window` days
      * `<m>_sd`        — trailing SD over the same window
      * `<m>_z`         — today's value in personal SD units (the honest "how unusual")
      * `<m>_pct_dev`   — today's value as % deviation from personal baseline
    """
    window = window or settings.baseline_window_days
    minp = max(7, window // 4)
    out = df.copy()

    out[LN_HRV] = np.log(out["hrv"].clip(lower=1))

    for metric in (LN_HRV, "resting_heart_rate", "respiratory_rate"):
        if metric not in out:
            continue
        g = out.groupby(ATHLETE_ID)[metric]
        base = _shifted_roll(g, window, "mean", minp)
        sd = _shifted_roll(g, window, "std", minp)
        out[f"{metric}_baseline"] = base
        out[f"{metric}_sd"] = sd
        # Guard against a degenerate window (an athlete with a flat metric) producing inf.
        out[f"{metric}_z"] = ((out[metric] - base) / sd.replace(0, np.nan)).replace(
            [np.inf, -np.inf], np.nan
        )

    # Percent deviation is reported on the raw ms scale because that is what an athlete
    # recognises, even though the z-score is computed in log space.
    hrv_base_ms = np.exp(out[f"{LN_HRV}_baseline"])
    out["hrv_baseline_rolling"] = hrv_base_ms
    out["hrv_pct_dev"] = 100 * (out["hrv"] - hrv_base_ms) / hrv_base_ms
    out["rhr_pct_dev"] = (
        100
        * (out["resting_heart_rate"] - out["resting_heart_rate_baseline"])
        / out["resting_heart_rate_baseline"]
    )
    return out


def add_load_dynamics(
    df: pd.DataFrame, acute: int | None = None, chronic: int | None = None
) -> pd.DataFrame:
    """Acute:chronic workload ratio, monotony and strain, all lagged by one day.

    * ACWR uses exponentially weighted averages rather than flat rolling means — the
      flat-mean formulation is the one most criticised in the ACWR literature for
      giving equal weight to a session 27 days ago and one yesterday.
    * Monotony is Foster's index (mean daily load / SD of daily load over the acute
      window); training *strain* is monotony x total load.
    """
    acute = acute or settings.acute_window_days
    chronic = chronic or settings.chronic_window_days
    out = df.copy()
    g = out.groupby(ATHLETE_ID)["day_strain"]

    prev = g.shift(1)
    out["load_acute"] = prev.ewm(halflife=acute / 2, min_periods=3).mean().reset_index(level=0, drop=True)
    out["load_chronic"] = (
        prev.ewm(halflife=chronic / 2, min_periods=10).mean().reset_index(level=0, drop=True)
    )
    out["acwr"] = (out["load_acute"] / out["load_chronic"].replace(0, np.nan)).replace(
        [np.inf, -np.inf], np.nan
    )

    roll = prev.rolling(acute, min_periods=max(3, acute // 2))
    mean_load, sd_load = roll.mean(), roll.std()
    out["monotony"] = (mean_load / sd_load.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan)
    out["training_strain_foster"] = out["monotony"] * (mean_load * acute)

    # Consecutive prior days with a completed workout, and days since a true rest day.
    wc = out.groupby(ATHLETE_ID)["workout_completed"].shift(1).fillna(0)
    rest_block = (wc == 0).groupby(out[ATHLETE_ID]).cumsum()
    out["consecutive_training_days"] = wc.groupby([out[ATHLETE_ID], rest_block]).cumsum()
    return out


def add_sleep_features(df: pd.DataFrame, window: int | None = None) -> pd.DataFrame:
    """Sleep debt, regularity and architecture proportions.

    Sleep "need" is taken as the athlete's own trailing median rather than a universal
    8 hours; individual sleep need varies substantially and a fixed target manufactures
    debt for short sleepers.
    """
    window = window or settings.baseline_window_days
    out = df.copy()
    g = out.groupby(ATHLETE_ID)["sleep_hours"]

    out["sleep_need_personal"] = _shifted_roll(g, window, "median", 7)
    out["sleep_deficit_h"] = (out["sleep_need_personal"] - out["sleep_hours"]).clip(lower=0)

    # Debt accumulates over the acute window and is lagged so it describes the state an
    # athlete woke up in, not one that includes tonight.
    deficit_prev = out.groupby(ATHLETE_ID)["sleep_deficit_h"].shift(1)
    out["sleep_debt_7d"] = (
        deficit_prev.rolling(settings.acute_window_days, min_periods=3).sum().reset_index(
            level=0, drop=True
        )
    )

    # Regularity: SD of sleep duration over the trailing window. High SD is the closest
    # proxy for social jetlag available without bed/wake timestamps.
    out["sleep_irregularity"] = _shifted_roll(g, window, "std", 7)

    total = out["sleep_hours"].replace(0, np.nan)
    out["pct_deep"] = 100 * out["deep_sleep_hours"] / total
    out["pct_rem"] = 100 * out["rem_sleep_hours"] / total
    out["pct_restorative"] = out["pct_deep"] + out["pct_rem"]
    return out


def add_intensity_features(df: pd.DataFrame) -> pd.DataFrame:
    """How the previous day's load was distributed across heart-rate zones.

    Total strain hides the difference between a 90-minute zone-2 ride and a 20-minute
    zone-5 interval session, and those two impose very different autonomic costs.
    """
    out = df.copy()
    zones = [f"hr_zone_{i}_min" for i in range(1, 6)]
    present = [z for z in zones if z in out]
    if not present:
        return out

    total = out[present].sum(axis=1).replace(0, np.nan)
    out["zone_minutes_total"] = total.fillna(0)
    out["high_intensity_min"] = out.get("hr_zone_4_min", 0) + out.get("hr_zone_5_min", 0)
    out["pct_high_intensity"] = (100 * out["high_intensity_min"] / total).fillna(0)

    # Edwards-style weighted load: minutes in each zone times the zone number.
    out["zone_weighted_load"] = sum(
        (i + 1) * out[z].fillna(0) for i, z in enumerate(present)
    )
    return out


def add_lags(df: pd.DataFrame, columns: list[str], lags: tuple[int, ...] = (1, 2, 3)) -> pd.DataFrame:
    """Append `<col>_lag<k>` for each requested column and lag."""
    out = df.copy()
    for col in columns:
        if col not in out:
            continue
        g = out.groupby(ATHLETE_ID)[col]
        for k in lags:
            out[f"{col}_lag{k}"] = g.shift(k)
    return out


def add_rolling_exposures(df: pd.DataFrame) -> pd.DataFrame:
    """Binary/ordinal behavioural exposures the causal engine can test.

    These stand in for the journal tags the WHOOP API exposes but this dataset lacks
    (alcohol, caffeine, stress). They are all derived from measured columns, so nothing
    here depends on self-report.
    """
    out = df.copy()
    g = lambda c: out.groupby(ATHLETE_ID)[c]

    out["short_sleep_prev"] = (g("sleep_hours").shift(1) < 6.5).astype("Int64")
    out["very_short_sleep_prev"] = (g("sleep_hours").shift(1) < 6.0).astype("Int64")
    out["high_strain_prev"] = (g("day_strain").shift(1) >= 14).astype("Int64")
    out["rest_day_prev"] = (g("workout_completed").shift(1) == 0).astype("Int64")

    if "workout_time_of_day" in out:
        out["late_workout_prev"] = (
            g("workout_time_of_day").shift(1).eq("Evening").astype("Int64")
        )

    out["fragmented_sleep_prev"] = (g("wake_ups").shift(1) >= 2).astype("Int64")
    out["acwr_spike"] = (out["acwr"] > 1.5).astype("Int64")
    out["acwr_undertraining"] = (out["acwr"] < 0.8).astype("Int64")

    # The compound exposure from the original product brief: two bad inputs together.
    out["double_hit_prev"] = (
        (out["short_sleep_prev"] == 1) & (out["high_strain_prev"] == 1)
    ).astype("Int64")

    out["illness_signal"] = (
        (out.get("respiratory_rate_z", pd.Series(np.nan, index=out.index)) > 1.5)
        | (out["skin_temp_deviation"].abs() > 1.0)
    ).astype("Int64")
    return out


DEFAULT_LAG_COLUMNS = [
    "day_strain",
    "sleep_hours",
    "sleep_efficiency",
    "hrv",
    LN_HRV,
    "resting_heart_rate",
    "recovery_score",
    "activity_strain",
    "high_intensity_min",
    "wake_ups",
    "pct_restorative",
]


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Run the whole pipeline in dependency order."""
    out = add_personal_baselines(df)
    out = add_load_dynamics(out)
    out = add_sleep_features(out)
    out = add_intensity_features(out)
    out = add_lags(out, DEFAULT_LAG_COLUMNS)
    out = add_rolling_exposures(out)
    return out


def feature_coverage(df: pd.DataFrame) -> pd.DataFrame:
    """Non-null coverage per derived feature.

    Rolling features are structurally missing for an athlete's first few weeks. The
    engine reports this so a null result is never confused with a thin one.
    """
    rows = []
    for c in sorted(df.columns):
        if c in (ATHLETE_ID, DATE):
            continue
        s = df[c]
        rows.append(
            {
                "feature": c,
                "n_non_null": int(s.notna().sum()),
                "pct_coverage": round(100 * s.notna().mean(), 1),
                "n_unique": int(s.nunique(dropna=True)),
            }
        )
    return pd.DataFrame(rows).sort_values("pct_coverage")
