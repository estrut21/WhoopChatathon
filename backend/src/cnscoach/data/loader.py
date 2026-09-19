"""Load a WHOOP-shaped daily panel from disk or from the live API.

Both sources satisfy `PanelSource`, so the causal engine, the CNS score and the coach
never learn which one they are running against.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Protocol, runtime_checkable

import pandas as pd

from cnscoach.config import settings
from cnscoach.data import schema as S

log = logging.getLogger(__name__)


@runtime_checkable
class PanelSource(Protocol):
    """Anything that can produce a canonical daily panel."""

    def load(self) -> pd.DataFrame: ...


# --------------------------------------------------------------------------------------


class CsvPanelSource:
    """The bundled 100k-row, 286-athlete research CSV."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path or settings.raw_csv)

    def load(self) -> pd.DataFrame:
        if not self.path.exists():
            raise FileNotFoundError(
                f"Dataset not found at {self.path}. Place whoop_fitness_dataset_100k.csv there, "
                "or point CNSCOACH_RAW_CSV at it."
            )
        raw = pd.read_csv(self.path)

        missing = set(S.CSV_TO_CANONICAL) - set(raw.columns)
        if missing:
            raise ValueError(f"CSV is missing expected columns: {sorted(missing)}")

        df = raw.rename(columns=S.CSV_TO_CANONICAL)
        df = df.drop(columns=[c for c in S.CSV_DEAD_COLUMNS if c in df.columns])
        return _normalise(df)


# --------------------------------------------------------------------------------------


class WhoopApiSource:
    """Live WHOOP v2 ingestion.

    Folds `/v2/cycle`, `/v2/recovery`, `/v2/activity/sleep` and `/v2/activity/workout`
    into the same canonical daily panel the CSV produces. Requires an OAuth access token
    with the scopes in `schema.WHOOP_V2_SCOPES`.
    """

    BASE_URL = "https://api.prod.whoop.com/developer"
    PAGE_LIMIT = 25  # WHOOP's documented maximum

    def __init__(self, access_token: str, start: str, end: str) -> None:
        self.access_token = access_token
        self.start = start
        self.end = end

    def _paginate(self, client, path: str) -> list[dict]:
        """Walk WHOOP's `nextToken` cursor until exhausted."""
        out: list[dict] = []
        params = {"start": self.start, "end": self.end, "limit": self.PAGE_LIMIT}
        while True:
            r = client.get(f"{self.BASE_URL}{path}", params=params)
            r.raise_for_status()
            payload = r.json()
            out.extend(payload.get("records", []))
            token = payload.get("next_token")
            if not token:
                return out
            params = {**params, "nextToken": token}

    def load(self) -> pd.DataFrame:
        import httpx

        headers = {"Authorization": f"Bearer {self.access_token}"}
        with httpx.Client(headers=headers, timeout=30.0) as client:
            cycles = self._paginate(client, S.WHOOP_V2_PATHS["cycle"])
            recoveries = self._paginate(client, S.WHOOP_V2_PATHS["recovery"])
            sleeps = self._paginate(client, S.WHOOP_V2_PATHS["sleep"])
            workouts = self._paginate(client, S.WHOOP_V2_PATHS["workout"])
            profile = client.get(f"{self.BASE_URL}{S.WHOOP_V2_PATHS['profile']}").json()
            body = client.get(f"{self.BASE_URL}{S.WHOOP_V2_PATHS['body']}").json()

        df = _fold_whoop_v2(cycles, recoveries, sleeps, workouts, profile, body)
        return _normalise(df)


def _fold_whoop_v2(
    cycles: list[dict],
    recoveries: list[dict],
    sleeps: list[dict],
    workouts: list[dict],
    profile: dict,
    body: dict,
) -> pd.DataFrame:
    """Join WHOOP's four record streams on cycle/day into one row per day."""
    athlete = str(profile.get("user_id", "me"))

    cyc = pd.DataFrame(
        [
            {
                "cycle_id": c["id"],
                S.DATE: pd.to_datetime(c["start"]).date(),
                "day_strain": (c.get("score") or {}).get("strain"),
                "calories_burned": (c.get("score") or {}).get("kilojoule", 0) / 4.184,
                "avg_heart_rate": (c.get("score") or {}).get("average_heart_rate"),
                "max_heart_rate": (c.get("score") or {}).get("max_heart_rate"),
            }
            for c in cycles
            if c.get("score_state") == "SCORED"
        ]
    )

    rec = pd.DataFrame(
        [
            {
                "cycle_id": r["cycle_id"],
                "recovery_score": (r.get("score") or {}).get("recovery_score"),
                "hrv": (r.get("score") or {}).get("hrv_rmssd_milli"),
                "resting_heart_rate": (r.get("score") or {}).get("resting_heart_rate"),
                "skin_temp_deviation": (r.get("score") or {}).get("skin_temp_celsius"),
                "user_calibrating": (r.get("score") or {}).get("user_calibrating", False),
            }
            for r in recoveries
            if r.get("score_state") == "SCORED"
        ]
    )

    def _sleep_row(s: dict) -> dict:
        sc = s.get("score") or {}
        st = sc.get("stage_summary") or {}
        hrs = lambda k: (st.get(k) or 0) / 3_600_000
        return {
            "cycle_id": s.get("cycle_id"),
            "light_sleep_hours": hrs("total_light_sleep_time_milli"),
            "rem_sleep_hours": hrs("total_rem_sleep_time_milli"),
            "deep_sleep_hours": hrs("total_slow_wave_sleep_time_milli"),
            "sleep_hours": (
                hrs("total_light_sleep_time_milli")
                + hrs("total_rem_sleep_time_milli")
                + hrs("total_slow_wave_sleep_time_milli")
            ),
            "wake_ups": st.get("disturbance_count"),
            "sleep_efficiency": sc.get("sleep_efficiency_percentage"),
            "respiratory_rate": sc.get("respiratory_rate"),
        }

    slp = pd.DataFrame(
        [_sleep_row(s) for s in sleeps if s.get("score_state") == "SCORED" and not s.get("nap")]
    )

    def _workout_row(w: dict) -> dict:
        sc = w.get("score") or {}
        z = sc.get("zone_durations") or {}
        mins = lambda k: (z.get(k) or 0) / 60_000
        return {
            S.DATE: pd.to_datetime(w["start"]).date(),
            "activity_type": w.get("sport_name"),
            "activity_strain": sc.get("strain"),
            "activity_calories": (sc.get("kilojoule") or 0) / 4.184,
            "activity_duration_min": (
                pd.to_datetime(w["end"]) - pd.to_datetime(w["start"])
            ).total_seconds()
            / 60,
            "hr_zone_1_min": mins("zone_one_milli"),
            "hr_zone_2_min": mins("zone_two_milli"),
            "hr_zone_3_min": mins("zone_three_milli"),
            "hr_zone_4_min": mins("zone_four_milli"),
            "hr_zone_5_min": mins("zone_five_milli"),
        }

    wk = pd.DataFrame([_workout_row(w) for w in workouts if w.get("score_state") == "SCORED"])
    if not wk.empty:
        # A day can hold several workouts; sum load, keep the longest session's label.
        agg = {c: "sum" for c in wk.columns if c not in (S.DATE, "activity_type")}
        longest = wk.sort_values("activity_duration_min").groupby(S.DATE)["activity_type"].last()
        wk = wk.groupby(S.DATE).agg(agg).join(longest).reset_index()

    df = cyc.merge(rec, on="cycle_id", how="left").merge(slp, on="cycle_id", how="left")
    if not wk.empty:
        df = df.merge(wk, on=S.DATE, how="left")

    df[S.ATHLETE_ID] = athlete
    df["weight_kg"] = body.get("weight_kilogram")
    df["height_cm"] = (body.get("height_meter") or 0) * 100 or None
    df["workout_completed"] = df.get("activity_strain", pd.Series(dtype=float)).fillna(0).gt(0).astype(int)

    # WHOOP reports skin temp in absolute °C here; convert to a personal deviation.
    if "skin_temp_deviation" in df:
        df["skin_temp_deviation"] = df["skin_temp_deviation"] - df["skin_temp_deviation"].median()

    return df.drop(columns=["cycle_id"])


# --------------------------------------------------------------------------------------


def _normalise(df: pd.DataFrame) -> pd.DataFrame:
    """Shared cleanup: types, sort order, derived basics, integrity checks."""
    df = df.copy()
    df[S.DATE] = pd.to_datetime(df[S.DATE])
    df[S.ATHLETE_ID] = df[S.ATHLETE_ID].astype(str)

    dupes = df.duplicated(subset=[S.ATHLETE_ID, S.DATE]).sum()
    if dupes:
        log.warning("Dropping %d duplicate (athlete, date) rows", dupes)
        df = df.drop_duplicates(subset=[S.ATHLETE_ID, S.DATE], keep="last")

    df = df.sort_values([S.ATHLETE_ID, S.DATE]).reset_index(drop=True)

    if "day_of_week" not in df:
        df["day_of_week"] = df[S.DATE].dt.day_name()
    if "sleep_hours" not in df and {"light_sleep_hours", "rem_sleep_hours", "deep_sleep_hours"} <= set(df):
        df["sleep_hours"] = df.light_sleep_hours + df.rem_sleep_hours + df.deep_sleep_hours

    df["is_weekend"] = df[S.DATE].dt.dayofweek.isin([5, 6]).astype(int)
    df["day_index"] = df.groupby(S.ATHLETE_ID).cumcount()

    return df


def load_panel(source: PanelSource | None = None) -> pd.DataFrame:
    """Load the canonical panel. Defaults to the bundled CSV."""
    return (source or CsvPanelSource()).load()


def panel_summary(df: pd.DataFrame) -> dict:
    """Facts about the loaded panel, used to ground the coach's claims about coverage."""
    per_athlete = df.groupby(S.ATHLETE_ID).size()
    return {
        "rows": len(df),
        "athletes": int(df[S.ATHLETE_ID].nunique()),
        "date_min": str(df[S.DATE].min().date()),
        "date_max": str(df[S.DATE].max().date()),
        "days_per_athlete_min": int(per_athlete.min()),
        "days_per_athlete_median": float(per_athlete.median()),
        "days_per_athlete_max": int(per_athlete.max()),
        "columns": sorted(df.columns.tolist()),
    }
