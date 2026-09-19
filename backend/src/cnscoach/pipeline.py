"""One place that assembles panel -> features -> findings, with an on-disk cache.

The full family takes about eight seconds on 100,000 rows, which is fine once and
intolerable on every Streamlit rerun. Results are cached against a fingerprint of the
inputs *and* of the hypothesis definitions, so editing a hypothesis or a ROPE
invalidates the cache automatically — a stale finding is worse than a slow one.
"""

from __future__ import annotations

import hashlib
import json
import logging
import pickle
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from cnscoach.causal.engine import Finding, family_summary, run_family, score_audit
from cnscoach.causal.hypotheses import HYPOTHESES
from cnscoach.config import settings
from cnscoach.data import build_features, load_panel, panel_summary

log = logging.getLogger(__name__)

CACHE_VERSION = 3


@dataclass
class Analysis:
    panel: pd.DataFrame
    features: pd.DataFrame
    findings: list[Finding]

    @property
    def summary(self) -> dict:
        return family_summary(self.findings)

    @property
    def audit(self) -> dict | None:
        return score_audit(self.findings)

    @property
    def coverage(self) -> dict:
        return panel_summary(self.panel)

    def athletes(self) -> list[str]:
        return sorted(self.panel["athlete_id"].unique().tolist())

    def finding(self, hypothesis_id: str) -> Finding:
        for f in self.findings:
            if f.hypothesis_id == hypothesis_id:
                return f
        raise KeyError(f"No finding '{hypothesis_id}'")


def _fingerprint(csv_path: Path) -> str:
    """Hash the inputs that could change the answer."""
    h = hashlib.sha256()
    h.update(str(CACHE_VERSION).encode())
    h.update(str(settings.alpha).encode())
    h.update(str(settings.baseline_window_days).encode())
    h.update(str(settings.acute_window_days).encode())
    h.update(str(settings.chronic_window_days).encode())

    if csv_path.exists():
        stat = csv_path.stat()
        h.update(f"{csv_path.name}:{stat.st_size}:{int(stat.st_mtime)}".encode())

    # Hypothesis definitions are part of the answer, so they are part of the key.
    spec = [
        [
            x.id,
            x.outcome,
            x.exposure,
            list(x.covariates),
            x.direction,
            x.rope_sd_frac,
        ]
        for x in HYPOTHESES
    ]
    h.update(json.dumps(spec, sort_keys=True).encode())
    return h.hexdigest()[:16]


def run_analysis(
    *,
    use_cache: bool = True,
    with_negative_controls: bool = True,
    n_permutations: int = 100,
    csv_path: Path | None = None,
) -> Analysis:
    """Load, engineer features, and run the pre-registered family."""
    settings.ensure_dirs()
    path = Path(csv_path or settings.raw_csv)
    cache_file = settings.cache_dir / f"analysis_{_fingerprint(path)}.pkl"

    if use_cache and cache_file.exists():
        try:
            with cache_file.open("rb") as fh:
                cached = pickle.load(fh)
            log.info("Loaded cached analysis from %s", cache_file.name)
            return cached
        except (pickle.UnpicklingError, EOFError, AttributeError, ImportError) as exc:
            log.warning("Cache unreadable (%s); recomputing", exc)

    from cnscoach.data.loader import CsvPanelSource

    panel = load_panel(CsvPanelSource(path))
    features = build_features(panel)
    findings = run_family(
        features,
        with_negative_controls=with_negative_controls,
        n_permutations=n_permutations,
    )

    analysis = Analysis(panel=panel, features=features, findings=findings)
    if use_cache:
        try:
            with cache_file.open("wb") as fh:
                pickle.dump(analysis, fh, protocol=pickle.HIGHEST_PROTOCOL)
        except OSError as exc:  # pragma: no cover
            log.warning("Could not write cache: %s", exc)
    return analysis


def clear_cache() -> int:
    """Remove cached analyses. Returns how many files were deleted."""
    if not settings.cache_dir.exists():
        return 0
    n = 0
    for f in settings.cache_dir.glob("analysis_*.pkl"):
        f.unlink()
        n += 1
    return n
