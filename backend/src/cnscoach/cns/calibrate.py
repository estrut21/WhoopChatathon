"""Refit CNS component weights against an outcome you choose.

The shipped `v0_autonomic` weights are a literature-informed prior, not a fitted result,
and the docstring says so. This module is how you replace the prior with evidence — and
how you find out whether doing so actually helps.

Two things make this honest rather than a curve-fitting exercise:

* **Athlete-level train/test split.** Days from one athlete never straddle the split.
  Fitting on days and testing on days from the same people reports a number that will
  not survive contact with a new user.
* **The prior is always evaluated too.** The output puts fitted and prior weights side
  by side with both out-of-sample R², so "the fit improved things" is a claim you can
  check rather than assume. On weakly-structured data it frequently does not.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from cnscoach.cns.base import ScoreContext
from cnscoach.cns.registry import DEFAULT_MODEL, get_model
from cnscoach.config import settings
from cnscoach.data.schema import ATHLETE_ID, DATE


@dataclass
class CalibrationResult:
    model_name: str
    outcome: str
    component_names: list[str]
    prior_weights: dict[str, float]
    fitted_weights: dict[str, float]
    r2_prior_test: float
    r2_fitted_test: float
    r2_fitted_train: float
    n_train_days: int
    n_test_days: int
    n_train_athletes: int
    n_test_athletes: int
    improved: bool
    notes: list[str]

    def summary(self) -> str:
        lines = [
            f"Calibration of {self.model_name} against '{self.outcome}'",
            f"  train {self.n_train_days:,} days / {self.n_train_athletes} athletes",
            f"  test  {self.n_test_days:,} days / {self.n_test_athletes} athletes",
            "",
            f"  {'component':<24} {'prior':>8} {'fitted':>8} {'delta':>8}",
        ]
        for c in self.component_names:
            p, f = self.prior_weights[c], self.fitted_weights[c]
            lines.append(f"  {c:<24} {p:8.3f} {f:8.3f} {f - p:+8.3f}")
        lines += [
            "",
            f"  out-of-sample R2, prior weights : {self.r2_prior_test:.4f}",
            f"  out-of-sample R2, fitted weights: {self.r2_fitted_test:.4f}",
            f"  in-sample R2,     fitted weights: {self.r2_fitted_train:.4f}",
            "",
            (
                "  VERDICT: refitting improves out-of-sample fit. Consider adopting."
                if self.improved
                else "  VERDICT: refitting does NOT improve out-of-sample fit. Keep the prior."
            ),
        ]
        lines.extend(f"  note: {n}" for n in self.notes)
        return "\n".join(lines)


def component_matrix(
    features: pd.DataFrame,
    model_name: str = DEFAULT_MODEL,
    *,
    athletes: list[str] | None = None,
    max_athletes: int | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    """Compute per-day component subscores for many athletes.

    Returns a frame of `athlete_id, date, sub_<component>...` plus the component order.
    """
    model = get_model(model_name)
    ids = athletes if athletes is not None else features[ATHLETE_ID].unique().tolist()
    if max_athletes is not None:
        ids = ids[:max_athletes]

    rows: list[dict] = []
    names: list[str] = []
    for aid in ids:
        sub = features[features[ATHLETE_ID] == aid].sort_values(DATE).reset_index(drop=True)
        for i in range(len(sub)):
            ctx = ScoreContext(
                athlete_id=aid, date=sub.at[i, DATE], today=sub.iloc[i], history=sub.iloc[:i]
            )
            r = model.score(ctx)
            if r.calibrating:
                continue
            if not names:
                names = [c.name for c in r.components]
            row = {ATHLETE_ID: aid, DATE: sub.at[i, DATE]}
            row.update({f"sub_{c.name}": c.subscore for c in r.components})
            rows.append(row)

    return pd.DataFrame(rows), names


def _r2(y: np.ndarray, yhat: np.ndarray) -> float:
    ss_res = float(np.sum((y - yhat) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    return 1 - ss_res / ss_tot if ss_tot > 0 else float("nan")


def calibrate_weights(
    features: pd.DataFrame,
    outcome: str,
    *,
    model_name: str = DEFAULT_MODEL,
    max_athletes: int | None = 60,
    test_fraction: float = 0.3,
    seed: int | None = None,
) -> CalibrationResult:
    """Fit non-negative component weights summing to 1, against `outcome`.

    `outcome` is whatever you decide readiness should predict — next-day performance,
    a subjective rating, time-to-exhaustion. The engine deliberately does not pick one
    for you, because that choice *is* the definition of readiness and it belongs to you.
    """
    rng = np.random.default_rng(seed if seed is not None else settings.random_seed)
    model = get_model(model_name)
    prior = dict(getattr(model, "weights", {}))
    notes: list[str] = []

    if outcome not in features.columns:
        raise KeyError(f"Outcome '{outcome}' not in panel")

    comps, names = component_matrix(features, model_name, max_athletes=max_athletes)
    if comps.empty:
        raise ValueError("No scoreable days — every day was still calibrating.")

    merged = comps.merge(
        features[[ATHLETE_ID, DATE, outcome]], on=[ATHLETE_ID, DATE], how="inner"
    ).dropna(subset=[outcome])

    # Within-athlete centring of the target: we are fitting what moves an athlete's
    # readiness day to day, not what distinguishes one athlete from another.
    merged["_y"] = merged[outcome] - merged.groupby(ATHLETE_ID)[outcome].transform("mean")
    notes.append(f"Outcome '{outcome}' centred within athlete before fitting.")

    athletes = merged[ATHLETE_ID].unique()
    rng.shuffle(athletes)
    n_test = max(1, int(len(athletes) * test_fraction))
    test_ids, train_ids = set(athletes[:n_test]), set(athletes[n_test:])

    train = merged[merged[ATHLETE_ID].isin(train_ids)]
    test = merged[merged[ATHLETE_ID].isin(test_ids)]
    cols = [f"sub_{n}" for n in names]

    Xtr, ytr = train[cols].to_numpy(float), train["_y"].to_numpy(float)
    Xte, yte = test[cols].to_numpy(float), test["_y"].to_numpy(float)

    # The weighted subscore is on a 0-100 scale while the centred outcome is not, so a
    # free scale and intercept are fitted alongside the weights. Only the weights are
    # reported — the scale is a nuisance parameter.
    def objective(params: np.ndarray, X: np.ndarray, y: np.ndarray) -> float:
        w, scale, intercept = params[: len(cols)], params[-2], params[-1]
        return float(np.mean((y - (scale * (X @ w) + intercept)) ** 2))

    x0 = np.array([*[prior.get(n, 1 / len(names)) for n in names], 0.1, 0.0])
    constraints = [{"type": "eq", "fun": lambda p: np.sum(p[: len(cols)]) - 1.0}]
    bounds = [(0.0, 1.0)] * len(cols) + [(-10, 10), (-100, 100)]

    fit = minimize(
        objective, x0, args=(Xtr, ytr), method="SLSQP", bounds=bounds, constraints=constraints
    )
    if not fit.success:  # pragma: no cover
        notes.append(f"Optimiser did not converge cleanly: {fit.message}")

    w_fit = fit.x[: len(cols)]
    fitted = {n: float(w) for n, w in zip(names, w_fit)}

    def _oos_r2(weights: np.ndarray) -> float:
        # Refit only scale and intercept on train, so both weight vectors get the same
        # treatment and the comparison is about the weights alone.
        sub = minimize(
            lambda p: float(np.mean((ytr - (p[0] * (Xtr @ weights) + p[1])) ** 2)),
            np.array([0.1, 0.0]),
            method="Nelder-Mead",
        )
        scale, intercept = sub.x
        return _r2(yte, scale * (Xte @ weights) + intercept)

    w_prior = np.array([prior.get(n, 1 / len(names)) for n in names])
    r2_prior_test = _oos_r2(w_prior)
    r2_fitted_test = _oos_r2(w_fit)

    scale_tr, int_tr = fit.x[-2], fit.x[-1]
    r2_fitted_train = _r2(ytr, scale_tr * (Xtr @ w_fit) + int_tr)

    if r2_fitted_train - r2_fitted_test > 0.05:
        notes.append(
            "In-sample R2 exceeds out-of-sample by more than 0.05 — the fit is picking "
            "up athlete-specific structure that will not generalise."
        )
    if max(r2_prior_test, r2_fitted_test) < 0.01:
        notes.append(
            "Both weight sets explain under 1% of out-of-sample variance. The component "
            "subscores carry almost no information about this outcome; changing weights "
            "cannot fix that."
        )

    return CalibrationResult(
        model_name=model_name,
        outcome=outcome,
        component_names=names,
        prior_weights={n: float(prior.get(n, np.nan)) for n in names},
        fitted_weights=fitted,
        r2_prior_test=float(r2_prior_test),
        r2_fitted_test=float(r2_fitted_test),
        r2_fitted_train=float(r2_fitted_train),
        n_train_days=len(train),
        n_test_days=len(test),
        n_train_athletes=len(train_ids),
        n_test_athletes=len(test_ids),
        improved=bool(r2_fitted_test > r2_prior_test),
        notes=notes,
    )
