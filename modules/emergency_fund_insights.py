"""
emergency_fund_insights.py — Streamlit render module for Chunk 6
Renders the Emergency Fund Planner & Financial Actions tab.
"""

from datetime import date

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.planning.emergency_fund import generate_milestone_report


def render(df: pd.DataFrame) -> None:
    """
    Render the Emergency Fund Planner tab.
    Accepts the full transactions DataFrame from the main app.
    """
    st.subheader("🛡️ Emergency Fund Planner & Financial Actions")
    st.caption(
        "Calculate your target emergency corpus, track your progress, "
        "and get personalized steps to reach your safety net."
    )

    # ── User Inputs ───────────────────────────────────────────────────────────
    st.markdown("#### Your Financial Details")
    c1, c2, c3 = st.columns(3)
    with c1:
        current_savings = st.number_input(
            "Current Liquid Savings (₹)", min_value=0.0, value=50000.0, step=1000.0,
            help="Cash in savings account, liquid MF, or FD that can be withdrawn quickly.",
        )
    with c2:
        monthly_contribution = st.number_input(
            "Planned Monthly Contribution (₹)", min_value=0.0, value=3000.0, step=500.0,
            help="How much you plan to add to your emergency fund each month.",
        )
    with c3:
        is_senior = st.checkbox(
            "Senior Citizen (60+)",
            help="Adds a 2-month medical buffer on top of the 6-month corpus target.",
        )

    custom_essential = None
    with st.expander("⚙️ Override Essential Expenses (optional)"):
        override = st.number_input(
            "Custom Monthly Essential Expenses (₹)", min_value=0.0, value=0.0, step=500.0,
            help="Leave at 0 to auto-detect from your transaction history.",
        )
        if override > 0:
            custom_essential = override

    st.markdown("---")

    # ── Validation ────────────────────────────────────────────────────────────
    if df.empty:
        st.warning("⚠️ No transaction data found. Please upload a CSV in the Dashboard tab first.")
        return

    # ── Generate Report ───────────────────────────────────────────────────────
    with st.spinner("Analysing your expense profile…"):
        report = generate_milestone_report(
            transactions=df,
            current_savings=current_savings,
            planned_monthly_contribution=monthly_contribution,
            is_senior=is_senior,
            custom_monthly_essential=custom_essential,
            currency="₹",
            as_of=date.today(),
        )

    profile = report.profile
    corpus  = report.corpus
    gap     = report.gap

    # ── Summary Cards ─────────────────────────────────────────────────────────
    m1, m2, m3, m4 = st.columns(4)
    for col, label, value, css in [
        (m1, "Monthly Essential",    f"₹{profile.monthly_essential:,.0f}",    "expense"),
        (m2, "Recommended Corpus",   f"₹{corpus.recommended_target:,.0f}",    "balance"),
        (m3, "Current Savings",      f"₹{gap.current_savings:,.0f}",          "income"),
        (m4, "Shortfall / Surplus",  f"₹{abs(gap.gap):,.0f} {'✅' if gap.is_funded else '⚠️'}", "income" if gap.is_funded else "expense"),
    ]:
        col.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value {css}">{value}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Summary Bullets ───────────────────────────────────────────────────────
    for line in report.summary_lines:
        st.markdown(f"- {line}")

    st.markdown("---")

    # ── Milestone Progress ────────────────────────────────────────────────────
    st.markdown("#### 📍 Savings Milestones")
    for ms in report.milestones:
        pct   = ms["pct_funded"]
        label = ms["label"]
        tgt   = ms["target"]
        eta   = ms["target_date"] or "—"
        mo    = ms["months"]

        col_label, col_bar, col_eta = st.columns([2, 4, 2])
        with col_label:
            st.markdown(f"**{label}**  \n₹{tgt:,.0f}")
        with col_bar:
            st.progress(int(pct))
            st.caption(f"₹{current_savings:,.0f} / ₹{tgt:,.0f} ({pct:.1f}%)")
        with col_eta:
            if pct >= 100:
                st.success("✅ Reached")
            elif mo is not None:
                st.info(f"~{mo} months\n({eta})")
            else:
                st.warning("No contribution set")

    st.markdown("---")

    # ── Projection Chart ──────────────────────────────────────────────────────
    st.markdown("#### 📈 Savings Growth Projection (24 Months)")
    if monthly_contribution > 0:
        months     = list(range(0, 25))
        projected  = [current_savings + monthly_contribution * m for m in months]
        proj_df    = pd.DataFrame({"Month": months, "Projected Savings (₹)": projected})

        fig = px.line(proj_df, x="Month", y="Projected Savings (₹)", markers=True,
                      color_discrete_sequence=["#60a5fa"])
        fig.add_hline(y=corpus.target_3m, line_dash="dot",  line_color="#facc15",
                      annotation_text="3-Month Target", annotation_position="bottom right")
        fig.add_hline(y=corpus.target_6m, line_dash="dash", line_color="#4ade80",
                      annotation_text="6-Month Target", annotation_position="bottom right")
        if is_senior:
            fig.add_hline(y=corpus.target_senior, line_dash="longdash", line_color="#f87171",
                          annotation_text="Senior Target", annotation_position="bottom right")
        fig.update_layout(margin=dict(t=10, b=10), paper_bgcolor="rgba(0,0,0,0)",
                          font_color="white", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, width="stretch")
    else:
        st.info("Set a monthly contribution above to see the projection chart.")

    st.markdown("---")

    # ── Category Breakdown ────────────────────────────────────────────────────
    if profile.category_breakdown:
        st.markdown("#### 🏷️ Monthly Expense Breakdown")
        cat_df = pd.DataFrame(
            list(profile.category_breakdown.items()),
            columns=["Category", "Monthly Avg (₹)"],
        ).sort_values("Monthly Avg (₹)", ascending=False)

        fig_cat = px.bar(
            cat_df, x="Monthly Avg (₹)", y="Category", orientation="h",
            color="Monthly Avg (₹)", color_continuous_scale="Reds",
        )
        fig_cat.update_layout(coloraxis_showscale=False, margin=dict(t=10, b=10),
                               paper_bgcolor="rgba(0,0,0,0)", font_color="white",
                               plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_cat, width="stretch")

    st.markdown("---")

    # ── Action Steps ──────────────────────────────────────────────────────────
    st.markdown("#### 💡 Personalized Action Steps")
    for step in report.action_steps:
        icon = "🔴" if step.priority == 1 else ("🟡" if step.priority == 2 else "🟢")
        with st.expander(f"{icon} Step {step.priority}: {step.action}"):
            st.markdown(step.detail)
            if step.monthly_impact > 0:
                st.caption(f"Estimated monthly impact: ₹{step.monthly_impact:,.0f}")

    st.markdown("---")

    # ── Downloadable Report ───────────────────────────────────────────────────
    st.markdown("#### 📥 Download Milestone Report")
    report_lines = ["# Emergency Fund Milestone Report", f"Generated: {report.generated_on}", ""]
    report_lines += ["## Summary"] + [f"- {l}" for l in report.summary_lines] + [""]
    report_lines += ["## Milestones"]
    for ms in report.milestones:
        report_lines.append(
            f"- {ms['label']}: ₹{ms['target']:,.0f} | "
            f"{ms['pct_funded']:.1f}% funded | ETA: {ms['target_date'] or '—'}"
        )
    report_lines += ["", "## Action Steps"]
    for step in report.action_steps:
        report_lines.append(f"{step.priority}. {step.action}: {step.detail}")

    st.download_button(
        "⬇️ Download Report (.txt)",
        data="\n".join(report_lines),
        file_name="emergency_fund_report.txt",
        mime="text/plain",
    )
