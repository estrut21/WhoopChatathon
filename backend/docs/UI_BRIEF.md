# UI brief — paste this whole file into Claude Code

You are building the front end for **cns-coach**, a hackathon project that does honest
statistical analysis of wearable (WHOOP-style) recovery data. The Python backend already
exists and is finished. Your job is the UI in **this** repository.

Read the whole brief before writing code. The product thesis drives almost every layout
decision here, so skipping to the endpoint list will produce the wrong UI.

---

## 1. What this product argues

Consumer recovery wearables give you a score every morning and a chatbot that will
confidently explain it. Three things they never do, and this product does:

1. **Distinguish "real" from "worth acting on."** With 100,000 athlete-days, an effect
   can be statistically certain and still far too small to change any decision. Most
   dashboards report the p-value and let you assume it matters.
2. **Say "no" affirmatively.** A non-significant result usually means "we found nothing."
   This engine runs equivalence tests, so it can say "we have positively ruled this out
   as a practical influence" — which is a *finding*, not an absence of one.
3. **Admit ignorance.** When the data cannot settle a question, it says so and reports
   the smallest effect it could have detected, instead of rounding down to "no effect."

**The single most important UI rule: null and trivial results get the same visual weight
as positive ones.** Do not tuck them behind a "show more" link, grey them out, or sort
them to the bottom. Hiding them is exactly the behaviour this project exists to argue
against. If you find yourself de-emphasising a `negligible` card because the page looks
empty, you have inverted the product.

### The headline finding

The analysis produced one result the whole demo is built around:

> Yesterday's training load is **detectable in raw HRV** (Holm-adjusted p = 1.9 × 10⁻⁶)
> but **not in the recovery score** (Holm-adjusted p = 1.00), even though the composite
> score is built from that same physiology. It retains roughly **19%** of the load
> signal present in its own input.

That is a concrete, checkable indictment of a proprietary metric. It should be the first
thing anyone sees.

---

## 2. Your task

Build UI in this repo for the surfaces in section 4.

**Match whatever stack already exists here.** Inspect the repo first — framework,
component library, styling approach, state management, file layout, naming conventions,
test setup — and follow it. Do not introduce a new framework, a new styling system, or a
new data-fetching library if one is already in use. If the repo is empty, use Next.js
(App Router) + TypeScript + Tailwind, and say so in your summary.

**Do not reimplement any statistics in the front end.** No recomputing p-values, no
re-deriving effect sizes, no "helpful" rounding that changes a number's meaning. Every
number you display comes from the API verbatim. If a value needs formatting, format it
for display only and keep the full precision in the DOM/tooltip.

---

## 3. The API

FastAPI backend, base URL `http://localhost:8000`, JSON everywhere, no auth.

Start it from the backend repo with:

```bash
uv run uvicorn cnscoach.api.main:app --reload
```

First request takes ~10 seconds (the analysis runs once at startup), then it is fast.

**If the backend is not running**, build against the fixtures in section 6 and keep the
data layer behind a single module so swapping to live calls is a one-line change. Put a
visible banner in the UI when you are serving mock data — a demo that silently shows
fake numbers is the failure mode this product is about.

### Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | `{status, findings, model, coach_enabled}` |
| GET | `/coverage` | What data exists — row counts, date range, column list |
| GET | `/findings?verdict=&outcome=` | All hypothesis results + family summary |
| GET | `/findings/{hypothesis_id}` | One result in full |
| GET | `/score-audit` | The headline finding |
| GET | `/athletes?limit=50` | `{n_total, athlete_ids}` |
| GET | `/athletes/{id}/cns?date=&model=` | Readiness score + full decomposition |
| GET | `/athletes/{id}/cns/trend?days=30&model=` | Score time series vs WHOOP's |
| GET | `/athletes/{id}/circularity?exposure=` | Is an exposure an ingredient of the score? |
| GET | `/models` | Registered scoring models |
| GET | `/evidence?query=&limit=5` | PubMed literature search |
| POST | `/ask` | `{question, athlete_id, strict}` → coach answer + verification |

`/ask` returns **503** when no Anthropic API key is configured on the backend. Handle
that as a normal state, not an error — show an explanatory empty state and keep the rest
of the page working.

### The five verdicts

Every finding carries exactly one. **They are not interchangeable and must be visually
distinct** — never collapse them into "significant / not significant."

| `verdict` | Means | Suggested treatment |
|---|---|---|
| `supported` | Detectable **and** big enough to act on | Green, strongest emphasis |
| `detectable_but_trivial` | Real, statistically solid, too small to act on | Amber. Must read as "true but ignore it" |
| `negligible` | Affirmatively ruled out by an equivalence test | Slate/neutral. **Frame as a result, not a blank** |
| `inconclusive` | Data cannot settle it | Purple. Always show `mde_80` alongside |
| `direction_reversed` | Real but opposite to the prediction | Red. Flag loudly |

The gap between `n_statistically_detectable` (3) and `n_practically_actionable` (1) in
the summary is the product's whole argument. Put both on screen, adjacent, labelled so
the difference is obvious.

---

## 4. Surfaces to build

### 4.1 Score audit — the landing view

From `GET /score-audit`. Two panels side by side: raw physiology vs the composite score,
each showing its coefficient, Holm-adjusted p-value and a detectable yes/no. Below them,
render `interpretation` verbatim as the conclusion — it is written to be quoted.

When `composite_discards_load_signal` is `true`, this is the money shot. Make it feel
like a verdict.

Also surface `signal_retention_ratio` (0.19) as a single number with a one-line gloss.

### 4.2 Findings table + detail

From `GET /findings`. A filterable table, plus an expandable detail view per row.

Detail view must show, for each finding:

- `quotable_claim` — a pre-written, statistically careful sentence. **Render it verbatim.**
  Do not paraphrase it; the phrasing is load-bearing.
- `coef` with `ci_low`–`ci_high`. **Never show a point estimate without its interval.**
- `p_adjusted` (Holm-corrected) — label it as corrected. If you also show `p_value`,
  label that as uncorrected.
- `pct_of_outcome_sd` — the effect as a share of a typical day-to-day swing. This is the
  most interpretable number on the screen; give it prominence.
- `mde_80` — the minimum detectable effect. **Required** on `inconclusive` findings.
- `confounding_note` — always visible, not behind a tooltip.
- `warnings[]` — if non-empty, show prominently.
- `dose_response[]` — a small bar chart with error bars (`ci_low`/`ci_high` per bin) when
  present. Note `dose_monotonic`.
- `negative_control` — if present, show `passes`. A failed negative control means the
  result may be an artifact and must be flagged.
- `pmids[]` — link each to `https://pubmed.ncbi.nlm.nih.gov/{pmid}/`.

### 4.3 CNS readiness score

From `GET /athletes/{id}/cns`. A transparent alternative to WHOOP's "Strain."

- Score 0–100, `band`, `confidence`.
- **The decomposition is the product.** Render every component as a horizontal bar of its
  `contribution`, with `subscore` × `weight` shown. They sum to the score — that
  invariant is enforced server-side, so your bars must visibly add up.
- Components with `available: false` had a missing input and were held at neutral. Mark
  them clearly; do not hide them.
- `caveats[]` — render all of them, visibly.
- When `calibrating` is `true`, **do not render a score at all.** Show the explanation
  instead: the personal baseline is too young for the number to mean anything. Resist
  showing a greyed-out number; that invites people to read it anyway.

Trend view from `/cns/trend`: plot `cns_score` and `recovery_score` together, in clearly
distinct colours. They are on different scales — add the caption "different scales, not
comparable in level; compare how they move."

### 4.4 Circularity check

From `/athletes/{id}/circularity?exposure=`. A dropdown of exposures; show whether the
chosen one is an ingredient of the score. When `circular` is `true`, render
`interpretation` as a warning with `contaminated_weight` as a percentage.

This exists because a readiness score built partly from training load will correlate with
training load *by construction*. It is an anti-self-congratulation feature; treat it as a
first-class surface, not a footnote.

### 4.5 Evidence

From `/evidence?query=`. Each result shows `short_citation`, `title`, `evidence_tier`
(study design) and links to `doi_url` and `url`.

Each curated paper has **both** a `supports` and a `does_not_support` field. **Render
both, with equal prominence.** One paper in the corpus reports HRV showing *little*
sensitivity to training load — the corpus says so rather than hiding it, and the UI must
too. Showing only `supports` would make the citations misleading.

Include the `attribution` string returned by the endpoint.

### 4.6 Coach

`POST /ask`. An LLM that may only cite retrieved data.

The response carries a `grounding` object. **This is not debug output — it is the
feature.** Display it:

- `grounding.summary` — a one-line verdict on whether every number checked out.
- `grounding.violations[]` — numbers the model produced that could not be traced to any
  retrieved datapoint. Show each with its `context` and `reason`, and strike through or
  visibly mark them in the answer text.
- `grounding.collision_rate` — the checker's measured false-negative rate (~3%). Show it.
  A guardrail that does not disclose its own strength is a claim, not a control.
- `citations[]` and `tool_calls[]` — show which tools were called to produce the answer.

A `blocked: true` response means strict mode withheld an ungrounded answer. Render the
refusal as a legitimate outcome, not an error toast.

---

## 5. Design constraints

- **Uncertainty is never optional.** Any coefficient on screen has its confidence
  interval next to it.
- **Never round in a way that changes meaning.** `p = 1.9e-06` may display as such;
  `p = 0.0000019` rounded to `p = 0.00` is a lie.
- **Use associational language in all copy you write.** "is followed by", "is associated
  with", "accompanies" — never "causes", "makes", "improves". Every result here is
  observational and nothing was randomised.
- **Do not write medical advice copy.** No "you should rest today."
- Prefer the backend's own strings (`quotable_claim`, `interpretation`, `explanation`,
  `caveats`) over prose you invent. They were written carefully to be defensible.
- Accessible colour contrast in both light and dark, and never encode verdict by colour
  alone — always pair with a text label.

---

## 6. Fixtures

Real responses, trimmed. Use these to build offline.

`GET /score-audit`:

```json
{
  "raw_signal": {
    "id": "A1_strain_to_hrv", "outcome": "hrv", "verdict": "detectable_but_trivial",
    "coef": -0.05339880519895325, "p_holm": 1.9463738185522704e-06,
    "pct_of_sd": -1.7368466756042693, "detectable": true
  },
  "composite": {
    "id": "C1_strain_to_recovery", "outcome": "recovery_score", "verdict": "negligible",
    "coef": 0.011296811108045066, "p_holm": 1.0,
    "pct_of_sd": 0.33045278752013396, "detectable": false
  },
  "signal_retention_ratio": 0.19,
  "composite_discards_load_signal": true,
  "interpretation": "Yesterday's training load is detectable in raw HRV (Holm p=1.9e-06) but not in the composite recovery score (Holm p=1), even though the composite is built from that same physiology. The composite retains roughly 19% of the load signal present in its own input. Whatever the score is summarising, it is not yesterday's load."
}
```

`GET /findings` (summary block + one finding):

```json
{
  "n": 17,
  "summary": {
    "n_hypotheses": 17,
    "verdicts": {"supported": 1, "detectable_but_trivial": 2, "negligible": 14,
                 "inconclusive": 0, "direction_reversed": 0},
    "n_statistically_detectable": 3,
    "n_practically_actionable": 1,
    "pct_detectable_but_not_actionable": 11.8,
    "pct_no_actionable_effect": 94.1,
    "alpha": 0.05,
    "correction": "Holm-Bonferroni, family-wise",
    "inference": "within-athlete fixed effects, cluster-robust SE on athlete, t(G-1)",
    "equivalence": "TOST against a per-hypothesis region of practical equivalence"
  },
  "findings": [{
    "hypothesis_id": "A1_strain_to_hrv",
    "family": "Training load to autonomic response",
    "question": "Does yesterday's cardiovascular load suppress this morning's HRV?",
    "verdict": "detectable_but_trivial",
    "outcome": "hrv", "exposure": "day_strain_lag1",
    "covariates": ["day_strain_lag2", "sleep_hours_lag1", "day_index", "is_weekend"],
    "coef": -0.05339880519895325, "se": 0.009857,
    "ci_low": -0.0727604, "ci_high": -0.0340372,
    "p_value": 1.216484e-07, "p_adjusted": 1.9463738185522704e-06,
    "n_obs": 99428, "n_athletes": 286, "r2_within": 0.0072,
    "pct_of_outcome_sd": -1.7368466756042693,
    "mde_80": 0.0277, "rope": 0.0922, "rope_sd_frac": 0.03,
    "equivalence_p": 4.97e-05, "realistic_swing": 11.7,
    "quotable_claim": "Does yesterday's cardiovascular load suppress this morning's HRV? The effect is real but too small to act on. It is statistically solid - a fall of 0.0534 ms per strain point yesterday (95% CI -0.0728 to -0.034 ms), Holm-adjusted p=1.9e-06 across 99,428 athlete-days from 286 athletes - and an equivalence test simultaneously bounds it below 3% of a typical day-to-day swing (p=5e-05). Across a realistic swing in day strain lag1 (11.7 units, the 10th-to-90th-percentile range within an athlete), that totals -0.626 ms. Believe it exists; do not change anything because of it.",
    "confounding_note": "Observational. High-strain days are chosen, not assigned - an athlete who feels good trains harder, which biases this toward zero if anything.",
    "pmids": ["37754967", "31642195", "33202732"],
    "warnings": [],
    "dose_monotonic": true,
    "dose_response": [
      {"bin_label": "(-0.001, 5.0]", "n": 13348, "mean": 1.837, "ci_low": 1.461, "ci_high": 2.213},
      {"bin_label": "(5.0, 8.0]",    "n": 23057, "mean": 1.440, "ci_low": 1.155, "ci_high": 1.725},
      {"bin_label": "(8.0, 11.0]",   "n": 25526, "mean": 0.444, "ci_low": 0.172, "ci_high": 0.716},
      {"bin_label": "(11.0, 14.0]",  "n": 18995, "mean": -1.306, "ci_low": -1.630, "ci_high": -0.982},
      {"bin_label": "(14.0, 17.0]",  "n": 11443, "mean": -2.124, "ci_low": -2.539, "ci_high": -1.709},
      {"bin_label": "(17.0, 21.0]",  "n": 7345,  "mean": -2.717, "ci_low": -3.227, "ci_high": -2.207}
    ],
    "negative_control": {
      "observed_coef": -0.05339880519895325, "null_mean": -0.0001,
      "permutation_p": 0.0, "n_permutations": 100, "passes": true
    }
  }]
}
```

`GET /athletes/USER_00001/cns`:

```json
{
  "score": 50.9, "band": "Adequate",
  "model_name": "v0_autonomic", "model_version": "0.1.0",
  "confidence": 1.0, "data_completeness": 1.0,
  "baseline_days_available": 200, "calibrating": false,
  "date": "2023-07-20", "athlete_id": "USER_00001",
  "components": [
    {"name": "autonomic_balance", "label": "Autonomic balance", "raw_value": -13.83,
     "subscore": 31.2, "weight": 0.35, "contribution": 10.92, "unit": "% vs baseline",
     "direction": "higher_is_better", "available": true,
     "rationale": "Overnight HRV relative to this athlete's own 28-day baseline, computed in log space because RMSSD is log-normal and raw means are pulled around by high outliers.",
     "pmids": ["37754967", "31642195", "30300066"], "inputs": ["ln_hrv_z", "hrv_pct_dev"]},
    {"name": "chronotropic_load", "label": "Chronotropic load", "raw_value": 5.50,
     "subscore": 36.0, "weight": 0.20, "contribution": 7.20, "unit": "% vs baseline",
     "direction": "lower_is_better", "available": true, "rationale": "Elevated resting heart rate against personal baseline indicates incomplete autonomic recovery, and moves more slowly than HRV.",
     "pmids": ["37754967", "31642195"], "inputs": ["resting_heart_rate_z", "rhr_pct_dev"]},
    {"name": "load_balance", "label": "Load balance (ACWR)", "raw_value": 0.99,
     "subscore": 100.0, "weight": 0.15, "contribution": 15.0, "unit": "ratio",
     "direction": "optimum_at_1.0", "available": true, "rationale": "Acute (7d) over chronic (28d) exponentially-weighted load. Penalised in both directions - a spike risks overreaching, a collapse is detraining.",
     "pmids": ["35344471", "33202732"], "inputs": ["acwr"]},
    {"name": "sleep_debt", "label": "Sleep debt (7d)", "raw_value": 2.78,
     "subscore": 44.4, "weight": 0.15, "contribution": 6.66, "unit": "h",
     "direction": "lower_is_better", "available": true, "rationale": "Accumulated shortfall against this athlete's own trailing median sleep need, not a universal 8-hour target.",
     "pmids": ["35409591"], "inputs": ["sleep_debt_7d"]},
    {"name": "sleep_quality", "label": "Restorative sleep", "raw_value": 43.52,
     "subscore": 83.2, "weight": 0.08, "contribution": 6.66, "unit": "% deep+REM",
     "direction": "higher_is_better", "available": true, "rationale": "Share of the night in slow-wave and REM sleep, against this athlete's own distribution.",
     "pmids": ["35409591"], "inputs": ["pct_restorative"]},
    {"name": "systemic_stress", "label": "Systemic stress", "raw_value": 0.31,
     "subscore": 63.3, "weight": 0.07, "contribution": 4.43, "unit": "SD / degC",
     "direction": "lower_is_better", "available": true, "rationale": "Respiratory-rate elevation and skin-temperature excursion. Worst-of rather than average, because either alone is enough reason to back off.",
     "pmids": ["35409591"], "inputs": ["respiratory_rate_z", "skin_temp_deviation"]}
  ],
  "caveats": [
    "Comparable to this athlete's own history only. Cross-athlete comparison of this score is not meaningful - the baselines differ.",
    "Partly built from training load (load_balance, weight 0.15). Do not cite this score's response to load as validation without a circularity check.",
    "Not a medical device and not validated against clinical outcomes."
  ]
}
```

`GET /athletes/USER_00001/circularity?exposure=day_strain_lag1`:

```json
{
  "exposure": "day_strain_lag1", "resolves_to": ["day_strain"], "circular": true,
  "implicated_components": [
    {"component": "load_balance", "label": "Load balance (ACWR)", "weight": 0.15, "via": ["day_strain"]}
  ],
  "contaminated_weight": 0.15, "clean_weight": 0.85,
  "interpretation": "15% of this score is built from 'day_strain_lag1'. Any association between the two is partly construction, not evidence. Compare using the remaining 85% of the score, or pick an exposure the score does not consume."
}
```

`POST /ask` (an ungrounded answer being caught):

```json
{
  "answer": "Strain is followed by a fall of 0.0534 ms in HRV, which translates to a [UNVERIFIED: 41]% reduction in training capacity.",
  "grounded": false, "blocked": false,
  "grounding": {
    "summary": "1 of 2 numeric claim(s) could NOT be traced to any retrieved data. Checker strength: a random plausible number would pass this 119-fact ledger 3.1% of the time.",
    "n_verified": 1, "n_violations": 1,
    "collision_rate": 0.031, "ledger_size": 119,
    "violations": [{
      "value": 41.0,
      "context": "0.0534 ms in HRV, which translates to a 41% reduction in training capacit",
      "reason": "no retrieved datapoint within +/-0.5 (the precision '41' was stated to)"
    }]
  },
  "tool_calls": [{"name": "get_finding", "args": {"hypothesis_id": "A1_strain_to_hrv"}}],
  "citations": []
}
```

`GET /coverage`: `rows` 100000, `athletes` 286, `date_min` "2023-01-01", `date_max`
"2024-02-03", `days_per_athlete_median` 351.5.

---

## 7. Important caveats to carry into the UI

State these plainly somewhere persistent — a footer or an About panel. They are not
disclaimers to bury; being upfront about them *is* the pitch.

- Everything is **observational**. No exposure was randomised.
- The bundled dataset is **simulated**, not measured from real people. Findings describe
  the dataset, not human physiology. The engine's credibility rests on a separate
  validation suite that recovers known planted effects, not on these numbers being
  medical facts.
- The dataset has **no journal tags** — no alcohol, caffeine, stress or mood columns.
  Questions about those cannot be answered, and the coach will say so.
- The CNS score is a **proposal**, not a validated clinical instrument.

---

## 8. When you are done

1. Run the project's linter/formatter and its test suite; fix what you broke.
2. Check every surface renders against both the live API and the fixtures.
3. Verify the honesty rules actually hold in the built UI — specifically: nulls are not
   hidden, no coefficient appears without its interval, `calibrating` shows no score, and
   `does_not_support` renders wherever `supports` does.
4. Commit following this repo's existing message conventions, and push to your branch.

In your final summary, list which surfaces you completed, anything you stubbed, and any
place where the backend contract did not match this brief.
