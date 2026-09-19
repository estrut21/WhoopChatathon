"""Dashboard.

Laid out around the argument rather than the data: the score audit comes first, then
the full verdict table including the nulls, then the CNS score decomposition, then the
coach with its grounding report visible. Nulls are shown with the same visual weight as
findings, on purpose — hiding them is the behaviour this project is arguing against.
"""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from cnscoach.causal.engine import VERDICT_PHRASING, Verdict, findings_to_frame
from cnscoach.cns import available as available_models
from cnscoach.cns import circularity_report, score_athlete_series, score_day
from cnscoach.config import settings
from cnscoach.evidence import ATTRIBUTION, EvidenceStore
from cnscoach.pipeline import run_analysis

st.set_page_config(page_title="cns-coach", layout="wide")

VERDICT_COLOR = {
    "supported": "#1a7f5a",
    "detectable_but_trivial": "#8a6d1f",
    "negligible": "#4a5568",
    "inconclusive": "#7a4f9c",
    "direction_reversed": "#a3352b",
}


@st.cache_resource(show_spinner="Running the pre-registered hypothesis family...")
def get_analysis():
    return run_analysis(use_cache=True)


@st.cache_resource
def get_evidence():
    return EvidenceStore()


@st.cache_data(show_spinner=False)
def get_trend(athlete_id: str, model: str, days: int) -> pd.DataFrame:
    return score_athlete_series(get_analysis().features, athlete_id, model_name=model, last_n=days)


analysis = get_analysis()

# ---------------------------------------------------------------------------- sidebar
with st.sidebar:
    st.title("cns-coach")
    st.caption("Honest longitudinal inference over wearable data")

    athletes = analysis.athletes()
    athlete = st.selectbox("Athlete", athletes, index=0)
    model_names = [m["name"] for m in available_models()]
    model = st.selectbox("CNS model", model_names, index=model_names.index("v0_autonomic"))
    window = st.slider("Trend window (days)", 14, 180, 60, step=7)

    st.divider()
    cov = analysis.coverage
    st.metric("Athlete-days", f"{cov['rows']:,}")
    st.metric("Athletes", cov["athletes"])
    st.caption(f"{cov['date_min']} to {cov['date_max']}")
    st.caption(f"Median {cov['days_per_athlete_median']:.0f} days/athlete")

    st.divider()
    st.caption(
        "Observational data. No exposure was randomised. The bundled dataset is "
        "simulated, so findings describe the dataset, not human physiology."
    )

# ---------------------------------------------------------------------------- header
st.title("Measurement is not improvement")
st.markdown(
    "Three things most recovery apps will not show you: **effects that are real but too "
    "small to act on**, **effects affirmatively ruled out**, and **questions the data "
    "cannot answer**. All three are on this page."
)

summary = analysis.summary
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Hypotheses tested", summary["n_hypotheses"])
c2.metric("Statistically detectable", summary["n_statistically_detectable"])
c3.metric("Worth acting on", summary["n_practically_actionable"])
c4.metric("Detectable, not actionable", f"{summary['pct_detectable_but_not_actionable']}%")
c5.metric("No actionable effect", f"{summary['pct_no_actionable_effect']}%")

st.caption(
    f"{summary['correction']} at alpha={summary['alpha']}. "
    f"Inference: {summary['inference']}. Equivalence: {summary['equivalence']}."
)

tabs = st.tabs(
    ["Score audit", "All findings", "CNS score", "Evidence", "Ask the coach", "Method"]
)

# ---------------------------------------------------------------------- 1. score audit
with tabs[0]:
    audit = analysis.audit
    if not audit:
        st.info("Score audit unavailable: the required hypotheses are not in the family.")
    else:
        st.subheader("Does the composite keep the signal its own inputs carry?")
        raw, comp = audit["raw_signal"], audit["composite"]

        left, right = st.columns(2)
        with left:
            st.markdown("**Raw physiology** &mdash; yesterday's load &rarr; HRV")
            st.metric(
                "Effect", f"{raw['coef']:+.4f} ms/strain pt",
                f"Holm p = {raw['p_holm']:.2g}",
            )
            st.markdown(f"Detectable: **{'yes' if raw['detectable'] else 'no'}**")
        with right:
            st.markdown("**Proprietary composite** &mdash; yesterday's load &rarr; recovery score")
            st.metric(
                "Effect", f"{comp['coef']:+.4f} pts/strain pt",
                f"Holm p = {comp['p_holm']:.2g}",
            )
            st.markdown(f"Detectable: **{'yes' if comp['detectable'] else 'no'}**")

        if audit["composite_discards_load_signal"]:
            st.error(audit["interpretation"])
        else:
            st.success(audit["interpretation"])

        if audit.get("signal_retention_ratio") is not None:
            st.caption(
                f"Signal retention ratio: {audit['signal_retention_ratio']:.2f} "
                "(composite effect size relative to raw, both standardised)."
            )

        st.divider()
        st.markdown("##### Dose-response in the raw signal")
        f = analysis.finding("A1_strain_to_hrv")
        if f.dose_response:
            dr = pd.DataFrame(f.dose_response)
            chart = (
                alt.Chart(dr)
                .mark_bar(color="#1a7f5a")
                .encode(
                    x=alt.X("bin_label:N", title="Yesterday's strain", sort=None),
                    y=alt.Y("mean:Q", title="Within-athlete HRV deviation (ms)"),
                    tooltip=["bin_label", "n", alt.Tooltip("mean:Q", format=".3f")],
                )
            )
            err = chart.mark_errorbar().encode(y="ci_low:Q", y2="ci_high:Q")
            st.altair_chart(chart + err, use_container_width=True)
            st.caption(
                f"Monotonic across bins: **{f.dose_monotonic}**. A significant "
                "coefficient with a non-monotonic dose-response usually means a "
                "threshold effect or an outlier-driven fit."
            )
        if f.negative_control:
            nc = f.negative_control
            st.caption(
                f"Negative control: shuffling the exposure within athlete gives a mean "
                f"coefficient of {nc['null_mean']:+.4f} versus the observed "
                f"{nc['observed_coef']:+.4f} (permutation p = {nc['permutation_p']:.3f}). "
                f"Passes: **{nc['passes']}**."
            )

# ---------------------------------------------------------------------- 2. findings
with tabs[1]:
    st.subheader("Every pre-registered hypothesis, including the nulls")

    chosen = st.multiselect(
        "Verdict",
        [v.value for v in Verdict],
        default=[v.value for v in Verdict],
        format_func=lambda v: VERDICT_PHRASING[Verdict(v)],
    )
    shown = [f for f in analysis.findings if f.verdict.value in chosen]

    st.dataframe(
        findings_to_frame(shown),
        use_container_width=True,
        hide_index=True,
        column_config={
            "p_raw": st.column_config.NumberColumn(format="%.2e"),
            "p_holm": st.column_config.NumberColumn(format="%.2e"),
        },
    )

    st.divider()
    for f in shown:
        colour = VERDICT_COLOR.get(f.verdict.value, "#4a5568")
        with st.expander(f"{f.hypothesis_id} — {f.question}"):
            st.markdown(
                f"<span style='background:{colour};color:white;padding:2px 8px;"
                f"border-radius:4px;font-size:0.85em'>"
                f"{VERDICT_PHRASING[f.verdict]}</span>",
                unsafe_allow_html=True,
            )
            st.write(f.quotable_claim)
            a, b, c = st.columns(3)
            a.metric("Coefficient", f"{f.coef:+.4f}")
            b.metric("95% CI", f"[{f.ci_low:+.3g}, {f.ci_high:+.3g}]")
            c.metric("Holm p", f"{f.p_adjusted:.2e}")
            a.metric("% of daily swing", f"{f.pct_of_outcome_sd:+.2f}%")
            b.metric("Min detectable effect", f"{f.mde_80:.4g}")
            c.metric("Athlete-days", f"{f.n_obs:,}")

            st.caption(f"**Confounding:** {f.confounding_note}")
            if f.warnings:
                for w in f.warnings:
                    st.warning(w)
            if f.pmids:
                st.caption("Mechanism references: " + ", ".join(f"PMID {p}" for p in f.pmids))

# ---------------------------------------------------------------------- 3. CNS score
with tabs[2]:
    st.subheader(f"CNS readiness — {athlete}")
    trend = get_trend(athlete, model, window)
    scored = trend[~trend.calibrating]

    if scored.empty:
        st.warning("Every day in this window is still calibrating; no score to show.")
    else:
        latest = score_day(analysis.features, athlete, scored.date.iloc[-1], model_name=model)
        a, b, c = st.columns([1, 1, 2])
        a.metric("CNS score", f"{latest.score:.0f}", latest.band)
        b.metric("Confidence", f"{latest.confidence:.0%}")
        c.metric(
            "WHOOP recovery (same day)",
            f"{scored.recovery_score.iloc[-1]:.0f}" if "recovery_score" in scored else "n/a",
        )

        melted = scored.melt(
            id_vars="date",
            value_vars=[c for c in ("cns_score", "recovery_score") if c in scored],
            var_name="metric",
            value_name="value",
        )
        st.altair_chart(
            alt.Chart(melted)
            .mark_line(point=False)
            .encode(
                x=alt.X("date:T", title=None),
                y=alt.Y("value:Q", title="Score", scale=alt.Scale(zero=False)),
                color=alt.Color(
                    "metric:N",
                    title=None,
                    scale=alt.Scale(
                        domain=["cns_score", "recovery_score"],
                        range=["#2dd4a7", "#f0a04b"],
                    ),
                    legend=alt.Legend(orient="top"),
                ),
                tooltip=["date:T", "metric:N", alt.Tooltip("value:Q", format=".1f")],
            )
            .properties(height=260),
            use_container_width=True,
        )
        st.caption(
            "The two scores are on different scales and are not comparable in level. "
            "Compare how they move."
        )

        st.divider()
        st.markdown("##### Decomposition — every component, weight and contribution")
        st.code(latest.explain(), language="text")

        comp_df = pd.DataFrame([c.to_dict() for c in latest.components])
        st.altair_chart(
            alt.Chart(comp_df)
            .mark_bar()
            .encode(
                x=alt.X("contribution:Q", title="Points contributed"),
                y=alt.Y("label:N", sort="-x", title=None),
                color=alt.Color("available:N", title="Input present"),
                tooltip=["label", "subscore", "weight", "contribution", "rationale"],
            )
            .properties(height=200),
            use_container_width=True,
        )

        st.divider()
        st.markdown("##### Circularity check")
        exposure = st.selectbox(
            "Test whether an exposure is an ingredient of this score",
            ["day_strain_lag1", "sleep_hours_lag1", "hrv", "wake_ups_lag1", "acwr"],
        )
        rep = circularity_report(latest, exposure)
        (st.error if rep["circular"] else st.success)(rep["interpretation"])

# ---------------------------------------------------------------------- 4. evidence
with tabs[3]:
    st.subheader("Literature (PubMed)")
    st.caption(
        "Mechanism only. A paper explains why an effect is plausible; it never says "
        "anything about this athlete, and the coach is forbidden from citing one to "
        "support a numeric claim."
    )
    query = st.text_input("Search", "training load autonomic recovery HRV")
    if query:
        for hit in get_evidence().search(query, limit=6):
            art = hit.article
            with st.expander(f"{art.short_citation} — {art.title[:80]}"):
                st.markdown(f"**{art.title}**")
                st.caption(f"Design: {art.evidence_tier}")
                if art.doi_url:
                    st.markdown(f"[DOI]({art.doi_url}) · [PubMed]({art.url})")
                if hit.curated_note:
                    st.success(f"**Supports:** {hit.curated_note['supports']}")
                    st.warning(f"**Does NOT support:** {hit.curated_note['does_not_support']}")
                if art.abstract:
                    st.caption(art.abstract[:700] + ("..." if len(art.abstract) > 700 else ""))
    st.caption(ATTRIBUTION)

# ---------------------------------------------------------------------- 5. coach
with tabs[4]:
    st.subheader("Ask the coach")
    st.caption(
        "The model starts with no data in context. It must retrieve everything through "
        "tools, and every number it emits is checked against what it actually retrieved."
    )

    if not settings.anthropic_api_key:
        st.info(
            "Set `CNSCOACH_ANTHROPIC_API_KEY` in `.env` to enable the coach. "
            "Everything else on this page works without it."
        )
    else:
        strict = st.toggle(
            "Strict mode (refuse rather than annotate)",
            value=False,
            help="Off: ungrounded numbers are marked inline. On: the whole reply is withheld.",
        )
        question = st.text_input(
            "Question", "Does my training load actually affect my recovery score?"
        )
        if st.button("Ask", type="primary"):
            from cnscoach.coach import Coach

            coach = Coach(
                analysis.features, analysis.findings, strict=strict, evidence=get_evidence()
            )
            with st.spinner("Retrieving and verifying..."):
                reply = coach.ask(question, athlete_id=athlete)

            (st.success if reply.is_grounded else st.error)(reply.grounding.summary())
            st.markdown(reply.text)

            if reply.grounding.violations:
                st.markdown("**Unverifiable claims:**")
                for v in reply.grounding.violations:
                    st.markdown(f"- `{v.value:g}` — {v.reason}")
            if reply.tool_calls:
                with st.expander(f"Tool calls ({len(reply.tool_calls)})"):
                    st.json(reply.tool_calls)
            if reply.citations:
                st.caption("Citations: " + "; ".join(reply.citations))

# ---------------------------------------------------------------------- 6. method
with tabs[5]:
    st.subheader("Method")
    st.markdown(
        """
**Within-athlete fixed effects.** Athletes differ enormously in baseline HRV, resting
heart rate and training volume. A pooled regression across 286 people mostly measures
*who is in the sample*. Every coefficient here absorbs an athlete intercept, so it
means: when this athlete's exposure is above their own average, their outcome moves by X.

**Cluster-robust standard errors on athlete.** Days within a person are serially
correlated. Treating 100,000 days as independent shrinks standard errors by roughly the
square root of days-per-athlete and manufactures significance. Critical values come from
`t(G-1)` with G = 286 clusters, because cluster-robust inference is asymptotic in the
number of clusters, not in the number of rows.

**Pre-registration and family-wise correction.** Every hypothesis is declared in
`causal/hypotheses.py` before results are seen, with its expected direction and its
region of practical equivalence. Holm-Bonferroni is applied across the whole family.
Adding a hypothesis widens the correction for all the others — that incentive is the
point.

**Equivalence testing (TOST).** A non-significant result is not evidence of absence.
Two one-sided tests against the region of practical equivalence let us say "this effect
is too small to matter" as a positive claim, and separately flag results that are merely
underpowered. Every null reports its minimum detectable effect.

**Negative controls.** Anything surviving correction is refitted with the exposure
shuffled within athlete. A real day-to-day relationship should vanish; one that survives
was an artifact of trend or seasonality.

**Circularity checks.** A readiness score built partly from training load will correlate
with training load by construction. Every score component declares its inputs so that
comparison can be caught rather than presented as validation.

**Guardrails.** Tool results are registered in a fact ledger; the coach's output is
checked against it, with tolerance derived from the precision each number was written to.
The checker reports its own measured false-negative rate, because a guardrail whose
strength is unknown is a claim, not a control.
        """
    )
    st.divider()
    st.markdown("##### Verify it yourself")
    st.code("uv run cnscoach validate", language="bash")
    st.caption(
        "Plants known effects in synthetic panels with athlete random intercepts and "
        "AR(1) serial correlation, then checks bias, CI coverage, standard-error "
        "calibration and the family-wise false-positive rate."
    )
