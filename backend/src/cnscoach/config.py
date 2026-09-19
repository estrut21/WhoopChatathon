"""Runtime configuration.

Everything that varies between a laptop demo and a real deployment lives here so the
analysis code never reaches for an environment variable directly.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env", env_prefix="CNSCOACH_", extra="ignore"
    )

    # ---- data ----
    data_dir: Path = REPO_ROOT / "data"
    raw_csv: Path = REPO_ROOT / "data" / "raw" / "whoop_fitness_dataset_100k.csv"
    cache_dir: Path = REPO_ROOT / "data" / "cache"
    evidence_dir: Path = REPO_ROOT / "data" / "evidence"

    # ---- statistics ----
    # Family-wise error rate for the pre-registered hypothesis family.
    alpha: float = 0.05
    # Athlete-level bootstrap resamples for cluster-robust intervals.
    bootstrap_draws: int = 1000
    # Minimum within-athlete observations before a per-athlete result is reported at all.
    min_obs_per_athlete: int = 30
    random_seed: int = 20260919

    # ---- baselines / features ----
    baseline_window_days: int = 28
    acute_window_days: int = 7
    chronic_window_days: int = 28

    # ---- PubMed (NCBI E-utilities) ----
    # An API key is optional; without one NCBI allows ~3 req/s, with one ~10 req/s.
    ncbi_api_key: str | None = None
    ncbi_email: str | None = None
    ncbi_tool: str = "cns-coach"
    pubmed_cache_ttl_days: int = 30

    # ---- LLM ----
    anthropic_api_key: str | None = None
    model: str = "claude-opus-5"
    max_tokens: int = 4096

    def ensure_dirs(self) -> None:
        for d in (self.cache_dir, self.evidence_dir):
            d.mkdir(parents=True, exist_ok=True)


settings = Settings()
