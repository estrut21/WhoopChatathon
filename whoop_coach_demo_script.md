# WHOOP Coach × PubMed — Demo Script

Cognitive Readiness agent. Reads the member's Whoop data, diagnoses the deviation, retrieves verified research, returns actionable guidance.

---

## Member state (Fri, Jul 7)

| | |
|---|---|
| **Cognitive Readiness** | **36% — LOW** (high confidence) |
| Daily Outlook | Depleted. Routine and administrative work only. |
| Sleep | 67% · Recovery 53% · Strain 10.9 |
| Stress | 1.3 medium (1:42 PM) |
| Health Monitor | Within range, 5/5 metrics |

**Score drivers**

| Driver | Points | z-score |
|---|---|---|
| HRV deviation | −9.6 | −1.53 |
| REM sleep | −7.8 | **−1.79** |
| Sleep debt | −7.3 | −1.01 |
| Resting heart rate | −3.2 | −0.74 |
| Deep sleep | **+3.3** | **+1.13** |
| Sleep continuity | −0.9 | −0.32 |

**Behind the score**

| | |
|---|---|
| HRV | 96.6 ms (baseline 115) |
| Resting HR | 75.9 bpm (baseline 74) |
| Sleep | 6:25 · 78.1% efficiency |
| REM | 1:19 |
| Deep | 1:16 |
| Wake-ups | 1 · 5 min to fall asleep |

---

## Turn 1

**Member**

> Hi Whoop, just got off work. I want to improve my cognitive readiness so I can work on my side hustle tonight and be wired. What should I do after my commute home?

**Coach**

Your read on today is off, and that changes what you should do.

You're assuming stress. Your data says otherwise — stress peaked at 1.3 and resting HR is 75.9 against a 74 baseline. Both normal. Work didn't do this.

What did: you slept 6h25m and your REM came in at 1h19m — a z-score of −1.79, the largest deviation in your profile. Deep sleep is *above* baseline. That split is the signature of a short night, not a hard day. Deep sleep front-loads and got protected; REM lives in the back third you didn't get to.

Sleep loss hits creative and divergent thinking hardest while rule-based work holds up — and stimulants restore alertness without restoring that function ([DOI](https://doi.org/10.1016/B978-0-444-53702-7.00007-5)). You can get wired tonight. You can't get sharp.

---

## Turn 2

**Member**

> But that doesn't solve my goal. I need to be cognitively ready for my side hustle tonight.

**Coach**

Fair — here's the plan to actually maximize tonight.

**Do all four, in this order:**

- **Walk 20 min now.** Acute aerobic exercise lifts executive function, g = 0.35, and fitness level doesn't change the effect ([DOI](https://doi.org/10.1111/psyp.12736))
- **200mg caffeine with the walk.** In sleep-deprived adults, 200mg roughly doubled performance vs. placebo — and 300mg was no better, so don't stack it ([DOI](https://doi.org/10.1007/s00213-018-5140-0)). Take it now so it clears before bed.
- **10 min paced breathing before you start.** Raises HRV, your top-weighted driver at −9.6 pts ([DOI](https://doi.org/10.1017/S0033291717001003))
- **Front-load the hard task.** Your first 90 minutes is the window. Don't spend it on email.

**One honest constraint:** caffeine restores alertness but doesn't fully restore performance to rested levels ([DOI](https://doi.org/10.1007/s00213-018-5140-0)), and divergent thinking stays impaired even when you feel sharp ([DOI](https://doi.org/10.1016/B978-0-444-53702-7.00007-5)). Put execution work in tonight's block — building, writing, shipping what you already planned. Save new strategy for a high-REM day.

Expect one strong 90-minute block, not three hours. Plan around that and you'll get more done than fighting for four.

---

## Turn 3

**Member**

> Why do I feel extra tired today?

**Coach**

Because it wasn't a bad night — it was a short one, and those feel different.

You fell asleep in 5 minutes and woke once. Quality was fine. But you got 6h25m total, and the piece that got cut was REM: 1h19m, z-score −1.79. Deep sleep actually came in above baseline. Short nights protect deep sleep and sacrifice REM, because REM lives in the back third you didn't get to.

That's why today feels heavier than the numbers you'd normally check. Your HRV is down too — 96.6 against a 115 baseline — which is your body catching up, not a new problem.

You're not unusual here. Sleep loss like this is common in working adults, and it hits the prefrontal cortex first, which is why it shows up as foggy thinking rather than physical tiredness ([DOI](https://doi.org/10.1016/B978-0-444-53702-7.00007-5)). Sleep duration and executive function follow a curve — there's an amount you need, and going under it costs you disproportionately ([DOI](https://doi.org/10.1007/s11910-023-01309-8)).

**The fix is one night, not a week.** Get 8 hours tonight and most of this clears.

---

## How the retrieval works

1. **Read the cycle.** Whoop payload is in context before the member speaks — metrics, z-scores against personal baseline, driver weights.
2. **Diagnose, don't echo.** "Why am I tired" is not a searchable query. The agent identifies which metric is actually deviant. Here: weight × deviation selects REM, not HRV, despite HRV carrying the higher feature weight.
3. **Translate to a physiological query.** Search the mechanism and the intervention, never the member's words.
4. **Two-pass retrieval.** Pass 1 establishes efficacy — broad query, filtered to `Meta-Analysis[pt] OR Systematic Review[pt] OR Randomized Controlled Trial[pt]`. Pass 2 adds MeSH age and activity terms for population modifiers.
5. **Evidence gate.** Pass 1 decides *what* to recommend. Pass 2 only adjusts dose, timing, framing. If pass 2 is thin, fall back to pass 1 — never substitute a small population-matched study for a large general one.
6. **Fit the study to the member.** Check study conditions against this person, right now. The agent will reject a paper it just retrieved.
7. **Deliver.** Their numbers first, 1–2 lines of research, 2–4 actions sized to tonight. DOI on every claim.
8. **Close the loop.** Each recommendation becomes a Journal behavior. Whoop's existing Impacts engine verifies it against their own data in 30 days.

---

## Sources

All retrieved live from PubMed.

| Claim | Source | Effect |
|---|---|---|
| Sleep loss degrades divergent thinking; stimulants don't restore it | Killgore 2010, *Prog Brain Res* · [DOI](https://doi.org/10.1016/B978-0-444-53702-7.00007-5) | Review |
| Acute aerobic exercise improves executive function | Ludyga et al. 2016, *Psychophysiology* · [DOI](https://doi.org/10.1111/psyp.12736) | g = 0.35 (40 studies) |
| HRV biofeedback reduces stress | Goessl et al. 2017, *Psychol Med* · [DOI](https://doi.org/10.1017/S0033291717001003) | g = 0.83 (24 studies, n = 484) |
| 200mg caffeine ≈ doubles performance under sleep loss; 300mg no better | Hansen et al. 2018, *Psychopharmacology* · [DOI](https://doi.org/10.1007/s00213-018-5140-0) | RCT, double-blind crossover |
| Sleep duration and executive function follow a quadratic curve | Sen & Tai 2023, *Curr Neurol Neurosci Rep* · [DOI](https://doi.org/10.1007/s11910-023-01309-8) | Review |

Research retrieved from PubMed. Wellness guidance, not medical advice.

---

## Pitch beats

**The premise contradiction.** Member says stressful day; data says medium stress and baseline RHR; the real answer is sleep architecture. A chatbot with a search tool cannot do this.

**The convergence.** The model already outputs "routine and administrative work only." PubMed independently explains *why* — convergent reasoning is spared, divergent reasoning isn't. Recommendation and literature arrive at the same place by different routes.

**The refusal.** The agent retrieves a paper and argues against applying it when the member's conditions don't match the study's.

**30-second version:** Whoop knows your physiology and has an LLM coach. What it can't do is tell you why, or show the evidence. We added a retrieval layer between them. It reads which metric is actually off, turns that into a physiological search — not your words — queries PubMed with study-design filters, and checks whether those studies apply to someone your age doing your activity at this hour. Then it logs the recommendation so your own data verifies it in 30 days.
