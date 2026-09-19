"""Canonical panel schema, and the mappings that get real data into it.

The engine only ever sees canonical column names. Two adapters feed it:

  * the bundled 100k-row research CSV (`CSV_TO_CANONICAL`), and
  * the live WHOOP v2 REST API (`WHOOP_V2_PATHS` / `whoop_v2_row`).

Keeping the mapping in one place is what makes "this runs on your own WHOOP account"
a one-adapter change rather than a rewrite.
"""

from __future__ import annotations

from dataclasses import dataclass

# --------------------------------------------------------------------------------------
# Canonical columns
# --------------------------------------------------------------------------------------

ATHLETE_ID = "athlete_id"
DATE = "date"

#: Columns that identify a row in the panel.
KEY_COLS: tuple[str, ...] = (ATHLETE_ID, DATE)

#: Time-invariant athlete attributes.
STATIC_COLS: tuple[str, ...] = (
    "age",
    "sex",
    "weight_kg",
    "height_cm",
    "fitness_level",
    "primary_sport",
    "hrv_baseline_reported",
    "rhr_baseline_reported",
)

#: Daily physiology / behaviour.
DAILY_COLS: tuple[str, ...] = (
    "recovery_score",
    "day_strain",
    "sleep_hours",
    "sleep_efficiency",
    "light_sleep_hours",
    "rem_sleep_hours",
    "deep_sleep_hours",
    "wake_ups",
    "sleep_latency_min",
    "hrv",
    "resting_heart_rate",
    "respiratory_rate",
    "skin_temp_deviation",
    "calories_burned",
    "workout_completed",
    "activity_type",
    "activity_duration_min",
    "activity_strain",
    "avg_heart_rate",
    "max_heart_rate",
    "activity_calories",
    "hr_zone_1_min",
    "hr_zone_2_min",
    "hr_zone_3_min",
    "hr_zone_4_min",
    "hr_zone_5_min",
    "workout_time_of_day",
    "day_of_week",
)

ALL_CANONICAL: tuple[str, ...] = KEY_COLS + STATIC_COLS + DAILY_COLS


# --------------------------------------------------------------------------------------
# Adapter 1: bundled research CSV
# --------------------------------------------------------------------------------------

CSV_TO_CANONICAL: dict[str, str] = {
    "user_id": ATHLETE_ID,
    "date": DATE,
    "day_of_week": "day_of_week",
    "age": "age",
    "gender": "sex",
    "weight_kg": "weight_kg",
    "height_cm": "height_cm",
    "fitness_level": "fitness_level",
    "primary_sport": "primary_sport",
    "recovery_score": "recovery_score",
    "day_strain": "day_strain",
    "sleep_hours": "sleep_hours",
    "sleep_efficiency": "sleep_efficiency",
    "light_sleep_hours": "light_sleep_hours",
    "rem_sleep_hours": "rem_sleep_hours",
    "deep_sleep_hours": "deep_sleep_hours",
    "wake_ups": "wake_ups",
    "time_to_fall_asleep_min": "sleep_latency_min",
    "hrv": "hrv",
    "resting_heart_rate": "resting_heart_rate",
    "hrv_baseline": "hrv_baseline_reported",
    "rhr_baseline": "rhr_baseline_reported",
    "respiratory_rate": "respiratory_rate",
    "skin_temp_deviation": "skin_temp_deviation",
    "calories_burned": "calories_burned",
    "workout_completed": "workout_completed",
    "activity_type": "activity_type",
    "activity_duration_min": "activity_duration_min",
    "activity_strain": "activity_strain",
    "avg_heart_rate": "avg_heart_rate",
    "max_heart_rate": "max_heart_rate",
    "activity_calories": "activity_calories",
    "hr_zone_1_min": "hr_zone_1_min",
    "hr_zone_2_min": "hr_zone_2_min",
    "hr_zone_3_min": "hr_zone_3_min",
    "hr_zone_4_min": "hr_zone_4_min",
    "hr_zone_5_min": "hr_zone_5_min",
    "workout_time_of_day": "workout_time_of_day",
}

#: Columns present in the CSV that carry no information and must never reach the engine.
#: `sleep_performance` is constant at 100.0 for all 100,000 rows.
CSV_DEAD_COLUMNS: tuple[str, ...] = ("sleep_performance",)


# --------------------------------------------------------------------------------------
# Adapter 2: WHOOP v2 REST API
# --------------------------------------------------------------------------------------

WHOOP_V2_PATHS = {
    "profile": "/v2/user/profile/basic",
    "body": "/v2/user/measurement/body",
    "cycle": "/v2/cycle",
    "sleep": "/v2/activity/sleep",
    "workout": "/v2/activity/workout",
    "recovery": "/v2/recovery",
}

WHOOP_V2_SCOPES = (
    "read:profile",
    "read:body_measurement",
    "read:cycles",
    "read:sleep",
    "read:workout",
    "read:recovery",
)

#: Canonical field <- dotted path inside the WHOOP v2 JSON payloads. Used by
#: `cnscoach.data.loader.WhoopApiSource` to fold four endpoints into one daily row.
WHOOP_V2_TO_CANONICAL: dict[str, str] = {
    # /v2/recovery
    "recovery_score": "recovery.score.recovery_score",
    "hrv": "recovery.score.hrv_rmssd_milli",
    "resting_heart_rate": "recovery.score.resting_heart_rate",
    "spo2_percentage": "recovery.score.spo2_percentage",
    "skin_temp_deviation": "recovery.score.skin_temp_celsius",
    # /v2/cycle
    "day_strain": "cycle.score.strain",
    "calories_burned": "cycle.score.kilojoule",
    "avg_heart_rate": "cycle.score.average_heart_rate",
    "max_heart_rate": "cycle.score.max_heart_rate",
    # /v2/activity/sleep
    "sleep_efficiency": "sleep.score.sleep_efficiency_percentage",
    "respiratory_rate": "sleep.score.respiratory_rate",
    "light_sleep_hours": "sleep.score.stage_summary.total_light_sleep_time_milli",
    "rem_sleep_hours": "sleep.score.stage_summary.total_rem_sleep_time_milli",
    "deep_sleep_hours": "sleep.score.stage_summary.total_slow_wave_sleep_time_milli",
    "wake_ups": "sleep.score.stage_summary.disturbance_count",
    # /v2/activity/workout
    "activity_strain": "workout.score.strain",
    "activity_type": "workout.sport_name",
    "hr_zone_1_min": "workout.score.zone_durations.zone_one_milli",
    "hr_zone_2_min": "workout.score.zone_durations.zone_two_milli",
    "hr_zone_3_min": "workout.score.zone_durations.zone_three_milli",
    "hr_zone_4_min": "workout.score.zone_durations.zone_four_milli",
    "hr_zone_5_min": "workout.score.zone_durations.zone_five_milli",
}

#: Canonical fields whose WHOOP source is in milliseconds and must be divided down.
WHOOP_MILLI_TO_HOURS = (
    "light_sleep_hours",
    "rem_sleep_hours",
    "deep_sleep_hours",
)
WHOOP_MILLI_TO_MINUTES = (
    "hr_zone_1_min",
    "hr_zone_2_min",
    "hr_zone_3_min",
    "hr_zone_4_min",
    "hr_zone_5_min",
)


@dataclass(frozen=True)
class ColumnDoc:
    """Human-readable provenance for a canonical column.

    The coach cites these when it explains where a number came from, which is how we
    keep it from inventing a metric WHOOP does not actually measure.
    """

    name: str
    unit: str
    description: str
    source: str


COLUMN_DOCS: dict[str, ColumnDoc] = {
    "recovery_score": ColumnDoc(
        "recovery_score", "%", "WHOOP's proprietary composite readiness score.", "WHOOP"
    ),
    "day_strain": ColumnDoc(
        "day_strain", "0-21", "WHOOP's logarithmic cardiovascular load for the cycle.", "WHOOP"
    ),
    "hrv": ColumnDoc(
        "hrv", "ms", "Overnight RMSSD heart-rate variability.", "WHOOP"
    ),
    "resting_heart_rate": ColumnDoc(
        "resting_heart_rate", "bpm", "Overnight resting heart rate.", "WHOOP"
    ),
    "sleep_hours": ColumnDoc(
        "sleep_hours", "h", "Total sleep time (light + REM + SWS).", "WHOOP"
    ),
    "sleep_efficiency": ColumnDoc(
        "sleep_efficiency", "%", "Asleep time divided by time in bed.", "WHOOP"
    ),
    "respiratory_rate": ColumnDoc(
        "respiratory_rate", "breaths/min", "Overnight respiratory rate.", "WHOOP"
    ),
    "skin_temp_deviation": ColumnDoc(
        "skin_temp_deviation", "°C", "Skin temperature deviation from personal baseline.", "WHOOP"
    ),
}
