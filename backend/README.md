# cns-coach

**Honest longitudinal inference over wearable data, a transparent readiness score, and a coach that cannot make things up.**

Built against a 100,000-row, 286-athlete daily WHOOP-shaped panel. Three problems with consumer recovery wearables, attacked directly:

| Problem | What this does |
|---|---|
| Chat answers point-in-time questions; nobody does rigorous causal inference over long horizons | A **pre-registered hypothesis family** run with within-athlete fixed effects, family-wise error control, and equivalence testing — so *"no effect"* and *"we can't tell"* are answers, not silences |
| Coaching LLMs fabricate data | A **citation-locked coach**. Every number it emits must trace to a retrieved datapoint; unsourced numbers are struck out or the reply is withheld. The checker reports its own measured miss rate (**3.1%**) |
| Proprietary composites like Strain are opaque | A **swappable CNS score** with every component, weight and citation in the open — plus a **score audit** that tests a composite against the raw signal it claims to summarise |

---

## The headline result

Running the family over the bundled panel produces a concrete, checkable indictment of the composite recovery score:

> Yesterday's training load is **detectable in raw HRV** (Holm-adjusted p = 1.9 × 10⁻⁶)
> but **not in the recovery score** (Holm-adjusted p = 1.00) — even though the composite
> is built from that same physiology. It retains roughly **19%** of the load signal
> present in its own input.

And 16 of 17 hypotheses come back as something other than "actionable finding":

| Verdict | Count | Meaning |
|---|---|---|
| `supported` | 1 | Detectable *and* big enough to act on |
| `detectable_but_trivial` | 2 | Real, statistically solid, too small to change behaviour |
| `negligible` | 14 | Affirmatively ruled out by an equivalence test |
| `inconclusive` | 0 | Data cannot settle it (reported with the minimum detectable effect) |
| `direction_reversed` | 0 | Real but backwards — flagged loudly |

Splitting those first two rows is the point. **3 results are statistically detectable; 1 is worth acting on.** At n = 100,000 those are different questions, and reporting only the first is how dashboards mislead.

---

## Why the statistics are the product

Most wearable analytics pool days across people and report a correlation. With 286 athletes and ~350 days each, that mostly measures *who is in the sample*. This engine instead:

- **absorbs an athlete intercept** on every estimate, so a coefficient means "when *this* athlete's exposure is above *their own* average";
- **clusters standard errors on athlete**, with the sandwich written out longhand in [`causal/estimators.py`](src/cnscoach/causal/estimators.py) so the degrees-of-freedom correction is auditable. Treating 100,000 serially-correlated days as independent shrinks SEs by roughly √(days per athlete) and manufactures significance. Critical values come from `t(G−1)`, because cluster-robust inference is asymptotic in the number of clusters (286), not rows;
- **corrects across the whole pre-registered family** (Holm–Bonferroni). Seventeen hypotheses at α = 0.05 uncorrected is a ~58% chance of at least one false discovery;
- **runs equivalence tests (TOST)**, so a bounded-small effect is an affirmative "this doesn't matter" rather than an absence of news;
- **reports the minimum detectable effect** on every null, so underpowered is never mistaken for negative;
- **runs permutation negative controls** on anything surviving correction — shuffle the exposure within athlete, and a real day-to-day relationship should vanish;
- **checks circularity** before comparing a score to an exposure, because a readiness score built partly from training load correlates with training load *by construction*.

### The engine is validated, not asserted

`uv run cnscoach validate` plants known effects in synthetic panels — with athlete random intercepts and AR(1) serial correlation, the two features that break naive analyses — and checks that they come back:

```
exposure -> outcome                  true      est     bias   SE/SD   cover   power
day_strain_lag1 -> hrv             -0.800   -0.795   +0.005    1.02   96.0%  100.0%  ok
sleep_hours_lag1 -> hrv             2.500    2.499   -0.001    1.11   96.0%  100.0%  ok
day_strain_lag1 -> recovery_score  -0.500   -0.476   +0.024    1.14   94.0%  100.0%  ok

family-wise false-positive rate : 2.0%  (nominal alpha 5.0%)
underpowered panel verdicts     : 2 inconclusive, 2 supported, 0 negligible
```

Unbiased, coverage at nominal, false positives controlled below α — and on a panel too small to see a real effect the engine says **inconclusive**, never **negligible**. Conflating "absent" with "invisible" is the specific dishonesty this project exists to prevent.

---

## The CNS score

A transparent replacement for Strain. Strain is a monotone function of cardiovascular work — it rises when the heart-rate integral rises and never looks at the *response*, so it cannot tell an athlete absorbing that work from one drowning in it. Readiness has to be a ratio of load to tolerance, and tolerance is observable in markers the device already records.

```
CNS score 51/100 (Adequate) [v0_autonomic v0.1.0, confidence 100%]

Built from:
  Load balance (ACWR)      100.0/100 x 0.15 =  15.0   [+0.99 ratio]
  Autonomic balance         31.2/100 x 0.35 =  10.9   [-13.83 % vs baseline]
  Chronotropic load         36.0/100 x 0.20 =   7.2   [+5.50 % vs baseline]
  Sleep debt (7d)           44.4/100 x 0.15 =   6.7   [+2.78 h]
  Restorative sleep         83.2/100 x 0.08 =   6.7   [+43.52 % deep+REM]
  Systemic stress           63.3/100 x 0.07 =   4.4   [+0.31 SD / degC]

  TOTAL                     50.9/100
```

Contributions must sum to the score and weights must sum to 1.0, enforced by `CNSResult.validate()` — a score that cannot be decomposed is not admissible. The weights are a **literature-informed prior, not a fitted result**, and the docstring says so; `cnscoach calibrate` refits them against any outcome you choose and reports out-of-sample R² for both the prior and the refit, so "the fit helped" is checkable.

**Writing your own** is one file. Copy [`cns/v1_template.py`](src/cnscoach/cns/v1_template.py), implement `score(ctx) -> CNSResult`, and `--cns-model your_name` works everywhere — CLI, API, dashboard. The engine, coach and UI talk to the protocol, never to a concrete model.

---

## The anti-Coach

The model starts with **no data in context**. It must retrieve everything through tools, every tool result registers its numbers into a **fact ledger**, and the final reply is verified against that ledger.

```
Input:  "Your recovery drops 18% after heavy training and HRV sits 23.7 ms below baseline."
Output: BLOCKED — 1 of 2 numeric claims could not be traced to any retrieved data.
        VIOLATION 23.7 — no retrieved datapoint within ±0.05
                         (the precision '23.7' was stated to)
```

Tolerance is derived from the **precision each number was written to**, not a flat percentage. A model that rounds 1.9464e-06 to `1.9e-06` is believed; a model that writes four significant figures is held to four.

**What it catches and what it doesn't.** It catches invented statistics — the dominant failure mode. It does not catch a fluent but wrong *qualitative* claim, and it cannot catch a number that collides with a real one by chance. That chance is measured and reported rather than assumed: **3.1%** on a typical 119-fact ledger. The rate grows with ledger size, which is why tools return curated fields rather than whole dataframes. A guardrail whose strength is unknown is a claim, not a control.

---

## Layout

```
src/cnscoach/
  data/       schema.py      canonical panel + CSV and WHOOP-v2 adapters
              loader.py      CsvPanelSource | WhoopApiSource (same interface)
              features.py    personal baselines, ACWR, sleep debt, monotony, lags
  causal/     hypotheses.py  the pre-registered family — edit this to ask new questions
              estimators.py  within-athlete FE, cluster-robust SE, TOST, Holm, bootstrap
              engine.py      orchestration, five verdicts, narration, score audit
              validation.py  plant known effects, confirm the engine recovers them
  cns/        base.py        CNSModel protocol, circularity checks  <-- the score slot
              v0_autonomic.py  literature-weighted default
              v1_template.py   copy this to write your own
              calibrate.py     refit weights, with an athlete-level train/test split
  evidence/   pubmed.py      NCBI E-utilities client with an on-disk cache
              corpus.py      hand-checked PMIDs, each with what it does NOT support
  coach/      tools.py       the coach's entire epistemic boundary
              guardrails.py  fact ledger, precision-aware verification
              agent.py       the tool-use loop
  pipeline.py                cached panel -> features -> findings
  api/main.py                FastAPI
  cli.py                     cnscoach ...
app/streamlit_app.py         dashboard
tests/                       63 tests
```

## Running it

```bash
uv sync
```

Run the full analysis and print the findings table:

```bash
uv run cnscoach analyze --verbose
```

Prove the engine works before trusting it:

```bash
uv run cnscoach validate
```

Score an athlete, with the full decomposition:

```bash
uv run cnscoach score --athlete USER_00001
```

Dashboard, API, literature search, and the coach:

```bash
uv run streamlit run app/streamlit_app.py
```
```bash
uv run uvicorn cnscoach.api.main:app --reload
```
```bash
uv run cnscoach evidence "training load autonomic recovery"
```
```bash
uv run cnscoach ask "does my training load actually affect my recovery score?" --strict
```

The coach needs `CNSCOACH_ANTHROPIC_API_KEY` in `.env` (see `.env.example`). Everything else runs without any credentials.

## Data

The bundled panel lives in `data/raw/` and is not committed. The same code path runs against a live WHOOP account by swapping `CsvPanelSource` for `WhoopApiSource` — the canonical schema and the full v2 endpoint mapping are both in [`data/schema.py`](src/cnscoach/data/schema.py), covering OAuth scopes, `nextToken` pagination and the millisecond/kilojoule unit conversions.

Literature is pulled live from PubMed via NCBI E-utilities and cached under `data/evidence/`, which *is* committed — so the project works offline and the exact record behind every citation is reviewable in the diff.

---

## Honesty notes

Kept here rather than buried, because they are load-bearing:

- **Everything is observational.** No exposure in this panel was randomised. The engine emits associational language and attaches a confounding note to every finding.
- **The bundled dataset is simulated, not measured from people.** Findings computed from it describe *the dataset*, not human physiology. `sleep_performance` is constant at 100.0 for all 100,000 rows and is dropped as a dead column. This is precisely why `cnscoach validate` exists: the claim being made is that the engine recovers known effects and correctly refuses absent ones, not that these particular numbers are medical facts.
- **There are no journal tags.** No alcohol, caffeine, stress or mood columns exist, so behavioural exposures are derived from measured columns instead. The coach is told to answer "I don't have that" rather than improvise.
- **The CNS score is a proposal, not a validated instrument.** It is not a medical device, has not been tested against clinical outcomes, and its weights are a prior.
- **The CNS score consumes training load** (`load_balance`, weight 0.15). Any comparison of the score against load is partly circular; `circularity_report()` exists to catch that and is wired into the dashboard, the API and the coach's tools.
