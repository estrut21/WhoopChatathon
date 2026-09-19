"""CNS readiness scoring: the pluggable replacement for opaque proprietary metrics."""

from __future__ import annotations

import pandas as pd

# Importing the concrete models is what populates the registry.
from cnscoach.cns import v0_autonomic as _v0  # noqa: F401
from cnscoach.cns import v1_template as _v1  # noqa: F401
from cnscoach.cns.base import (
    MIN_BASELINE_DAYS,
    CNSModel,
    CNSResult,
    Component,
    ScoreContext,
    band_for,
    circularity_report,
    resolve_primitives,
)
from cnscoach.cns.registry import DEFAULT_MODEL, available, get_model, register
from cnscoach.data.schema import ATHLETE_ID, DATE

__all__ = [
    "DEFAULT_MODEL",
    "MIN_BASELINE_DAYS",
    "CNSModel",
    "CNSResult",
    "Component",
    "ScoreContext",
    "available",
    "band_for",
    "circularity_report",
    "get_model",
    "register",
    "resolve_primitives",
    "score_athlete_series",
    "score_day",
]


def score_day(
    features: pd.DataFrame,
    athlete_id: str,
    date: str | pd.Timestamp | None = None,
    model_name: str = DEFAULT_MODEL,
) -> CNSResult:
    """Score one athlete-day. `date=None` means that athlete's most recent day.

    The default is resolved per athlete, not panel-wide: athletes in this dataset stop
    reporting on different days, so a panel-level `max(date)` simply does not exist for
    most of them.
    """
    model = get_model(model_name)
    sub = features[features[ATHLETE_ID] == athlete_id].sort_values(DATE)
    if sub.empty:
        raise KeyError(f"No athlete '{athlete_id}'")

    date = sub[DATE].max() if date is None else pd.Timestamp(date)
    match = sub[sub[DATE] == date]
    if match.empty:
        raise KeyError(
            f"No row for {athlete_id} on {date.date()}. That athlete's data covers "
            f"{sub[DATE].min().date()} to {sub[DATE].max().date()}."
        )

    ctx = ScoreContext(
        athlete_id=athlete_id,
        date=date,
        today=match.iloc[0],
        history=sub[sub[DATE] < date],
    )
    return model.score(ctx)


def score_athlete_series(
    features: pd.DataFrame,
    athlete_id: str,
    model_name: str = DEFAULT_MODEL,
    *,
    last_n: int | None = None,
) -> pd.DataFrame:
    """Score every day for one athlete, returning a tidy frame.

    The history window is sliced by position rather than re-filtered by date on each
    iteration, which keeps a full 350-day athlete well under a second.
    """
    model = get_model(model_name)
    sub = features[features[ATHLETE_ID] == athlete_id].sort_values(DATE).reset_index(drop=True)
    if sub.empty:
        raise KeyError(f"No athlete '{athlete_id}'")

    start = 0 if last_n is None else max(0, len(sub) - last_n)
    rows = []
    for i in range(start, len(sub)):
        ctx = ScoreContext(
            athlete_id=athlete_id,
            date=sub.at[i, DATE],
            today=sub.iloc[i],
            history=sub.iloc[:i],
        )
        r = model.score(ctx)
        row = {
            DATE: sub.at[i, DATE],
            "cns_score": r.score,
            "band": r.band,
            "confidence": r.confidence,
            "calibrating": r.calibrating,
            "completeness": r.data_completeness,
        }
        for c in r.components:
            row[f"c_{c.name}"] = c.contribution
            row[f"sub_{c.name}"] = c.subscore
        rows.append(row)

    out = pd.DataFrame(rows)
    # Carry the incumbent metrics alongside so the two can be compared directly.
    for col in ("recovery_score", "day_strain", "hrv", "resting_heart_rate"):
        if col in sub:
            out[col] = sub.loc[start:, col].to_numpy()
    return out
