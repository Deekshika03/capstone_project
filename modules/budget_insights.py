import streamlit as st
import pandas as pd
import plotly.express as px


def _get_monthly_expenses(expense_df: pd.DataFrame) -> pd.DataFrame:
    """Return a DataFrame with Month and total expense Amount, sorted chronologically."""
    monthly = (
        expense_df.groupby("Month")["Amount"]
        .apply(lambda x: abs(x).sum())
        .reset_index()
    )
    monthly.columns = ["Month", "Spent"]
    # Sort by actual date order using the first Date in each month
    month_order = (
        expense_df.sort_values("Date")["Month"].unique().tolist()
    )
    monthly["Month"] = pd.Categorical(monthly["Month"], categories=month_order, ordered=True)
    return monthly.sort_values("Month").reset_index(drop=True)


def _spending_suggestions(cat_totals: pd.Series) -> list[str]:
    """Return simple rule-based suggestions based on category spending."""
    suggestions = []
    thresholds = {
        "Food": 300,
        "Shopping": 200,
        "Entertainment": 150,
        "Transport": 150,
        "Bills": 250,
    }
    for cat, limit in thresholds.items():
        if cat in cat_totals.index and cat_totals[cat] > limit:
            suggestions.append(
                f"💡 Your **{cat}** spending (${cat_totals[cat]:,.2f}) is above the "
                f"suggested ${limit}. Consider reviewing these expenses."
            )
    if not suggestions:
        suggestions.append("✅ Great job! Your spending looks well-balanced across all categories.")
    return suggestions


def render(expense_df: pd.DataFrame) -> None:
    """Render the Smart Spending Insights & Budget Alerts module."""

    st.subheader("📋 Monthly Budget Setup")

    if expense_df.empty:
        st.warning("⚠️ No expense data found. Please upload a file with expense transactions.")
        return

    # ── Month selector ────────────────────────────────────────────────────────
    available_months = (
        expense_df.sort_values("Date")["Month"].unique().tolist()
    )
    selected_month = st.selectbox("Select month to analyse", available_months, index=len(available_months) - 1)

    current_df = expense_df[expense_df["Month"] == selected_month]
    actual_expense = abs(current_df["Amount"].sum())

    # ── Budget input ──────────────────────────────────────────────────────────
    budget = st.number_input(
        "Set your monthly budget ($)",
        min_value=0.0,
        value=1500.0,
        step=50.0,
        format="%.2f",
    )

    if budget <= 0:
        st.error("❌ Please enter a budget greater than $0.")
        return

    remaining = budget - actual_expense
    pct_used = (actual_expense / budget) * 100

    # ── Summary metrics ───────────────────────────────────────────────────────
    m1, m2, m3 = st.columns(3)
    m1.metric("Monthly Budget", f"${budget:,.2f}")
    m2.metric("Total Spent", f"${actual_expense:,.2f}", delta=f"-${actual_expense:,.2f}", delta_color="inverse")
    m3.metric(
        "Remaining Budget",
        f"${remaining:,.2f}",
        delta=f"{'Over by' if remaining < 0 else 'Left'} ${abs(remaining):,.2f}",
        delta_color="inverse" if remaining < 0 else "normal",
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Alerts ────────────────────────────────────────────────────────────────
    if pct_used >= 100:
        st.error(f"🚨 **Budget Exceeded!** You've spent ${actual_expense:,.2f} of your ${budget:,.2f} budget ({pct_used:.1f}%).")
    elif pct_used >= 80:
        st.warning(f"⚠️ **Heads-up!** You've used {pct_used:.1f}% of your budget. Only ${remaining:,.2f} remaining.")
    else:
        st.success(f"✅ You're on track! {pct_used:.1f}% of budget used.")

    # ── Progress bar ──────────────────────────────────────────────────────────
    st.markdown("**Budget Usage**")
    st.progress(min(pct_used / 100, 1.0))
    st.caption(f"${actual_expense:,.2f} spent of ${budget:,.2f} ({pct_used:.1f}%)")

    st.divider()

    # ── Category breakdown ────────────────────────────────────────────────────
    st.subheader("🏷️ Spending by Category")

    cat_totals = (
        current_df.groupby("Category")["Amount"]
        .apply(lambda x: abs(x).sum())
        .sort_values(ascending=False)
    )

    if cat_totals.empty:
        st.info("No category data available for the selected month.")
        return

    top_cat = cat_totals.idxmax()
    st.info(f"🔝 Highest-spending category this month: **{top_cat}** (${cat_totals[top_cat]:,.2f})")

    col_bar, col_gauge = st.columns(2)

    with col_bar:
        cat_df = cat_totals.reset_index()
        cat_df.columns = ["Category", "Spent"]
        fig = px.bar(
            cat_df, x="Spent", y="Category", orientation="h",
            color="Spent", color_continuous_scale="Reds",
            labels={"Spent": "Amount ($)", "Category": ""},
        )
        fig.update_layout(coloraxis_showscale=False, margin=dict(t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)

    with col_gauge:
        fig_gauge = px.pie(
            cat_df, values="Spent", names="Category",
            hole=0.5,
            color_discrete_sequence=px.colors.qualitative.Set2,
            title="Category Share",
        )
        fig_gauge.update_traces(textposition="inside", textinfo="percent+label")
        fig_gauge.update_layout(showlegend=False, margin=dict(t=40, b=10))
        st.plotly_chart(fig_gauge, use_container_width=True)

    st.divider()

    # ── Month-over-month comparison ───────────────────────────────────────────
    st.subheader("📈 Month-over-Month Category Comparison")

    monthly_expenses = _get_monthly_expenses(expense_df)

    if len(available_months) >= 2:
        prev_month = available_months[available_months.index(selected_month) - 1] if available_months.index(selected_month) > 0 else None

        if prev_month:
            prev_df = expense_df[expense_df["Month"] == prev_month]
            prev_cat = prev_df.groupby("Category")["Amount"].apply(lambda x: abs(x).sum())
            curr_cat = current_df.groupby("Category")["Amount"].apply(lambda x: abs(x).sum())

            comparison = pd.DataFrame({"Previous": prev_cat, "Current": curr_cat}).fillna(0)
            comparison["Change"] = comparison["Current"] - comparison["Previous"]
            increased = comparison[comparison["Change"] > 0].sort_values("Change", ascending=False)

            if not increased.empty:
                st.warning(f"📊 Categories with **increased spending** vs {prev_month}:")
                for cat, row in increased.iterrows():
                    st.markdown(f"- **{cat}**: ${row['Previous']:,.2f} → ${row['Current']:,.2f} (+${row['Change']:,.2f})")
            else:
                st.success(f"✅ No category spending increased compared to {prev_month}.")

            # Side-by-side bar chart
            comp_df = comparison.reset_index().melt(id_vars="Category", value_vars=["Previous", "Current"], var_name="Period", value_name="Amount")
            fig_comp = px.bar(
                comp_df, x="Category", y="Amount", color="Period", barmode="group",
                color_discrete_map={"Previous": "#94a3b8", "Current": "#f87171"},
                labels={"Amount": "Amount ($)"},
            )
            fig_comp.update_layout(legend_title_text="", margin=dict(t=10, b=10))
            st.plotly_chart(fig_comp, use_container_width=True)
        else:
            st.info("ℹ️ No previous month available for comparison.")
    else:
        st.info("ℹ️ Upload data with at least 2 months to see month-over-month comparison.")

    st.divider()

    # ── Budget trend across months ────────────────────────────────────────────
    st.subheader("📉 Monthly Spending Trend vs Budget")

    fig_trend = px.line(
        monthly_expenses, x="Month", y="Spent",
        markers=True, labels={"Spent": "Amount ($)", "Month": ""},
        color_discrete_sequence=["#f87171"],
    )
    fig_trend.add_hline(
        y=budget, line_dash="dash", line_color="#60a5fa",
        annotation_text=f"Budget ${budget:,.0f}", annotation_position="top left",
    )
    fig_trend.update_layout(margin=dict(t=10, b=10))
    st.plotly_chart(fig_trend, use_container_width=True)

    st.divider()

    # ── Personalized suggestions ──────────────────────────────────────────────
    st.subheader("💬 Personalized Spending Suggestions")
    for tip in _spending_suggestions(cat_totals):
        st.markdown(tip)
