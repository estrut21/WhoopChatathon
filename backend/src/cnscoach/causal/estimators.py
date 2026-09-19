"""Estimators for within-athlete longitudinal inference.

Design notes, because the defaults in most libraries are wrong for this data shape:

* **Within-athlete fixed effects.** Athletes differ enormously in baseline HRV, RHR and
  training volume. A pooled regression across 286 people mostly measures *who* is in the
  sample, not what changes within a person. Every estimate here absorbs an athlete
  intercept, so a coefficient means "when this athlete's exposure is above their own
  average, their outcome moves by X".

* **Cluster-robust standard errors, clustered on athlete.** Days within an athlete are
  serially correlated; treating 100,000 days as 100,000 independent observations shrinks
  standard errors by roughly sqrt(days-per-athlete) and manufactures significance. The
  sandwich is written out longhand below so the degrees-of-freedom correction is
  auditable rather than a library default.

* **Critical values from t(G-1), not the normal.** With G clusters, cluster-robust
  inference is only asymptotic in G, not in N. Here G = 286.

* **Equivalence testing.** A non-significant result is not evidence of no effect. TOST
  lets us say "the effect is smaller than anything that would matter" as a positive
  claim, and separately flags results that are merely underpowered.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats

from cnscoach.config import settings
from cnscoach.data.schema import ATHLETE_ID


@dataclass
class Estimate:
    """One coefficient, with everything needed to judge whether to believe it."""

    term: str
    coef: float
    se: float
    t_stat: float
    p_value: float
    ci_low: float
    ci_high: float
    df: int
    n_obs: int
    n_clusters: int

    # Interpretability
    coef_per_exposure_sd: float = np.nan
    pct_of_outcome_sd: float = np.nan
    exposure_sd: float = np.nan
    outcome_sd: float = np.nan

    # Post-hoc, filled by the engine
    p_adjusted: float | None = None
    mde_80: float = np.nan
    equivalence_p: float | None = None
    rope: float | None = None

    @property
    def significant(self) -> bool:
        p = self.p_adjusted if self.p_adjusted is not None else self.p_value
        return bool(p < settings.alpha)

    @property
    def ci_excludes_zero(self) -> bool:
        return (self.ci_low > 0) or (self.ci_high < 0)

    def to_dict(self) -> dict:
        return {k: (None if isinstance(v, float) and np.isnan(v) else v) for k, v in self.__dict__.items()}


@dataclass
class FitResult:
    """A fitted within-athlete model."""

    outcome: str
    terms: list[str]
    estimates: dict[str, Estimate]
    n_obs: int
    n_clusters: int
    r2_within: float
    dropped_for_missing: int
    warnings: list[str] = field(default_factory=list)

    def get(self, term: str) -> Estimate:
        return self.estimates[term]


# --------------------------------------------------------------------------------------
# Core fit
# --------------------------------------------------------------------------------------


def _demean(frame: pd.DataFrame, cols: Sequence[str], group: pd.Series) -> pd.DataFrame:
    """Subtract each athlete's own mean from every column (the within transform)."""
    out = frame[list(cols)].copy()
    for c in cols:
        out[c] = out[c] - out[c].groupby(group).transform("mean")
    return out


def within_athlete_fe(
    df: pd.DataFrame,
    outcome: str,
    exposures: Sequence[str],
    covariates: Sequence[str] = (),
    *,
    group_col: str = ATHLETE_ID,
    min_obs_per_athlete: int | None = None,
) -> FitResult:
    """Fit `outcome ~ exposures + covariates` with athlete fixed effects absorbed.

    Returns cluster-robust inference with critical values from t(G-1).
    """
    min_obs = min_obs_per_athlete or settings.min_obs_per_athlete
    terms = [*exposures, *covariates]
    needed = [outcome, *terms, group_col]

    missing_cols = [c for c in needed if c not in df.columns]
    if missing_cols:
        raise KeyError(f"Columns not in panel: {missing_cols}")

    n_before = len(df)
    data = df[needed].replace([np.inf, -np.inf], np.nan).dropna()
    warnings: list[str] = []

    # Athletes with too few usable days contribute noise to the within transform.
    counts = data.groupby(group_col).size()
    keep = counts[counts >= min_obs].index
    dropped_athletes = int(counts.shape[0] - len(keep))
    if dropped_athletes:
        warnings.append(
            f"{dropped_athletes} athlete(s) dropped for fewer than {min_obs} complete days"
        )
    data = data[data[group_col].isin(keep)]

    if data.empty or data[group_col].nunique() < 3:
        raise ValueError(f"Not enough data to fit {outcome} ~ {terms}")

    groups = data[group_col]
    w = _demean(data, [outcome, *terms], groups)

    # Drop terms with no within-athlete variance (e.g. a constant exposure).
    live_terms = []
    for t in terms:
        if np.isclose(w[t].std(ddof=0), 0):
            warnings.append(f"'{t}' has no within-athlete variance and was dropped")
        else:
            live_terms.append(t)
    if not live_terms:
        raise ValueError(f"No terms with within-athlete variance for outcome '{outcome}'")

    y = w[outcome].to_numpy(dtype=float)
    X = w[live_terms].to_numpy(dtype=float)

    n, k = X.shape
    g_codes, uniques = pd.factorize(groups, sort=True)
    G = len(uniques)

    XtX = X.T @ X
    try:
        XtX_inv = np.linalg.inv(XtX)
    except np.linalg.LinAlgError as exc:  # pragma: no cover - collinear inputs
        raise ValueError(f"Collinear design for {outcome} ~ {live_terms}") from exc

    beta = XtX_inv @ (X.T @ y)
    resid = y - X @ beta

    # --- cluster-robust sandwich -------------------------------------------------
    # meat = sum_g (X_g' u_g)(X_g' u_g)'  -- accumulated with a scatter-add over clusters.
    Xu = X * resid[:, None]
    meat = np.zeros((k, k))
    sums = np.zeros((G, k))
    np.add.at(sums, g_codes, Xu)
    meat = sums.T @ sums

    # Absorbed athlete intercepts count against the residual df.
    df_resid = n - G - k
    if df_resid <= 0:  # pragma: no cover - guarded by min_obs
        raise ValueError("Non-positive residual degrees of freedom")
    correction = (G / (G - 1)) * ((n - 1) / df_resid)
    vcov = correction * (XtX_inv @ meat @ XtX_inv)
    se = np.sqrt(np.diag(vcov))

    # Inference uses t(G-1): cluster-robust SEs are asymptotic in the number of clusters.
    t_df = G - 1
    t_stats = beta / se
    p_values = 2 * stats.t.sf(np.abs(t_stats), df=t_df)
    t_crit = stats.t.ppf(1 - settings.alpha / 2, df=t_df)

    tss = float(np.sum(y**2))
    r2_within = float(1 - np.sum(resid**2) / tss) if tss > 0 else np.nan

    # Power: the smallest effect this design could detect 80% of the time.
    t_power = stats.t.ppf(0.80, df=t_df)
    mde = se * (t_crit + t_power)

    outcome_sd = float(w[outcome].std(ddof=1))
    estimates: dict[str, Estimate] = {}
    for i, term in enumerate(live_terms):
        exp_sd = float(w[term].std(ddof=1))
        estimates[term] = Estimate(
            term=term,
            coef=float(beta[i]),
            se=float(se[i]),
            t_stat=float(t_stats[i]),
            p_value=float(p_values[i]),
            ci_low=float(beta[i] - t_crit * se[i]),
            ci_high=float(beta[i] + t_crit * se[i]),
            df=int(t_df),
            n_obs=int(n),
            n_clusters=int(G),
            coef_per_exposure_sd=float(beta[i] * exp_sd),
            pct_of_outcome_sd=float(100 * beta[i] * exp_sd / outcome_sd) if outcome_sd else np.nan,
            exposure_sd=exp_sd,
            outcome_sd=outcome_sd,
            mde_80=float(mde[i]),
        )

    return FitResult(
        outcome=outcome,
        terms=live_terms,
        estimates=estimates,
        n_obs=int(n),
        n_clusters=int(G),
        r2_within=r2_within,
        dropped_for_missing=int(n_before - len(data)),
        warnings=warnings,
    )


# --------------------------------------------------------------------------------------
# Multiplicity, equivalence, power, negative controls
# --------------------------------------------------------------------------------------


def holm_bonferroni(p_values: Sequence[float]) -> np.ndarray:
    """Holm step-down adjusted p-values, monotonicity enforced.

    Controls family-wise error across the pre-registered hypothesis family. Running
    twenty hypotheses at alpha=0.05 without this yields roughly a 64% chance of at
    least one false "discovery" — precisely the failure mode this project exists to
    avoid.
    """
    p = np.asarray(list(p_values), dtype=float)
    m = len(p)
    if m == 0:
        return p
    order = np.argsort(p)
    adjusted = np.empty(m, dtype=float)
    running = 0.0
    for rank, idx in enumerate(order):
        val = (m - rank) * p[idx]
        running = max(running, val)
        adjusted[idx] = min(1.0, running)
    return adjusted


def tost_equivalence(est: Estimate, rope: float) -> float:
    """Two one-sided tests against a region of practical equivalence of +/- `rope`.

    Returns the TOST p-value. p < alpha means we can affirmatively claim the effect is
    too small to matter, rather than merely failing to detect one.
    """
    if rope <= 0:
        raise ValueError("ROPE must be positive")
    t_lower = (est.coef + rope) / est.se
    t_upper = (est.coef - rope) / est.se
    p_lower = stats.t.sf(t_lower, df=est.df)  # H0: beta <= -rope
    p_upper = stats.t.cdf(t_upper, df=est.df)  # H0: beta >= +rope
    return float(max(p_lower, p_upper))


def permutation_negative_control(
    df: pd.DataFrame,
    outcome: str,
    exposure: str,
    covariates: Sequence[str] = (),
    *,
    n_permutations: int = 200,
    seed: int | None = None,
) -> dict:
    """Shuffle the exposure within athlete and refit; the effect should vanish.

    A real lagged relationship survives only when day alignment is preserved. If a
    shuffled exposure reproduces the effect, the finding is an artifact of trend or
    seasonality rather than a day-to-day relationship.
    """
    rng = np.random.default_rng(seed if seed is not None else settings.random_seed)
    observed = within_athlete_fe(df, outcome, [exposure], covariates).get(exposure)

    work = df[[ATHLETE_ID, outcome, exposure, *covariates]].dropna().copy()
    null_coefs: list[float] = []
    for _ in range(n_permutations):
        shuffled = work.copy()
        shuffled[exposure] = (
            shuffled.groupby(ATHLETE_ID)[exposure]
            .transform(lambda s: rng.permutation(s.to_numpy()))
        )
        try:
            null_coefs.append(within_athlete_fe(shuffled, outcome, [exposure], covariates).get(exposure).coef)
        except (ValueError, KeyError):  # pragma: no cover - degenerate resample
            continue

    null = np.asarray(null_coefs)
    exceedance = float(np.mean(np.abs(null) >= abs(observed.coef))) if null.size else np.nan
    return {
        "observed_coef": observed.coef,
        "observed_p": observed.p_value,
        "null_mean": float(null.mean()) if null.size else np.nan,
        "null_sd": float(null.std(ddof=1)) if null.size > 1 else np.nan,
        "null_abs_p95": float(np.percentile(np.abs(null), 95)) if null.size else np.nan,
        "permutation_p": exceedance,
        "n_permutations": int(null.size),
        "passes": bool(exceedance < 0.05) if null.size else False,
    }


def cluster_bootstrap_ci(
    df: pd.DataFrame,
    outcome: str,
    exposure: str,
    covariates: Sequence[str] = (),
    *,
    n_draws: int | None = None,
    seed: int | None = None,
) -> dict:
    """Percentile CI from resampling *athletes* with replacement.

    A second opinion on the sandwich estimator that makes no distributional assumption.
    Resampling athletes rather than days preserves within-person serial correlation.
    """
    n_draws = n_draws or settings.bootstrap_draws
    rng = np.random.default_rng(seed if seed is not None else settings.random_seed)

    cols = [ATHLETE_ID, outcome, exposure, *covariates]
    work = df[cols].replace([np.inf, -np.inf], np.nan).dropna()
    athletes = work[ATHLETE_ID].unique()
    by_athlete = {a: g for a, g in work.groupby(ATHLETE_ID)}

    coefs: list[float] = []
    for _ in range(n_draws):
        picked = rng.choice(athletes, size=len(athletes), replace=True)
        # Relabel so an athlete drawn twice contributes two distinct fixed effects.
        frames = []
        for j, a in enumerate(picked):
            f = by_athlete[a].copy()
            f[ATHLETE_ID] = f"{a}__{j}"
            frames.append(f)
        sample = pd.concat(frames, ignore_index=True)
        try:
            coefs.append(
                within_athlete_fe(sample, outcome, [exposure], covariates, min_obs_per_athlete=1)
                .get(exposure)
                .coef
            )
        except (ValueError, KeyError, np.linalg.LinAlgError):  # pragma: no cover
            continue

    arr = np.asarray(coefs)
    if arr.size < 20:  # pragma: no cover - pathological input
        return {"n_draws": int(arr.size), "ci_low": np.nan, "ci_high": np.nan}
    lo, hi = np.percentile(arr, [100 * settings.alpha / 2, 100 * (1 - settings.alpha / 2)])
    return {
        "n_draws": int(arr.size),
        "boot_mean": float(arr.mean()),
        "boot_se": float(arr.std(ddof=1)),
        "ci_low": float(lo),
        "ci_high": float(hi),
    }


def dose_response(
    df: pd.DataFrame,
    outcome: str,
    exposure: str,
    bins: Sequence[float],
    *,
    group_col: str = ATHLETE_ID,
) -> pd.DataFrame:
    """Within-athlete mean outcome by exposure bin.

    Monotonicity across bins is weak evidence for a real relationship; a significant
    coefficient with a non-monotonic dose-response usually indicates a threshold effect
    or an outlier-driven fit.
    """
    work = df[[group_col, outcome, exposure]].replace([np.inf, -np.inf], np.nan).dropna().copy()
    work["_w"] = work[outcome] - work.groupby(group_col)[outcome].transform("mean")
    work["_bin"] = pd.cut(work[exposure], bins=list(bins), include_lowest=True)

    g = work.groupby("_bin", observed=True)["_w"]
    out = g.agg(n="size", mean="mean", sd="std").reset_index()
    out["se"] = out["sd"] / np.sqrt(out["n"])
    out["ci_low"] = out["mean"] - 1.96 * out["se"]
    out["ci_high"] = out["mean"] + 1.96 * out["se"]
    out["bin_label"] = out["_bin"].astype(str)

    diffs = out["mean"].diff().dropna()
    out.attrs["monotonic"] = bool((diffs >= 0).all() or (diffs <= 0).all())
    return out.drop(columns=["_bin"])
