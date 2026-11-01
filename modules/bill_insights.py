"""
bill_insights.py — Module component for rendering Recurring Bills, EMIs, and Alerts in tabs.
"""

from datetime import date
import pandas as pd
import plotly.express as px
import streamlit as st

from src.planning.bill_tracker import (
    AlertPriority,
    BillTracker,
    generate_simulated_transactions,
)


def render(df: pd.DataFrame) -> None:
    """Render Recurring Bills & EMI detection within a tab or component."""
    st.subheader("💳 Recurring Bills, EMI Detector & Alert System")

    if df.empty:
        st.warning("⚠️ No transaction data available. Please upload a CSV file with transactions.")
        return

    # Check if there are recurring bills in the uploaded data
    tracker = BillTracker(df, as_of_date=None, min_occurrences=2)

    # If the user dataset doesn't have multiple recurring months yet, offer simulated demonstration
    if not tracker.recurring_bills:
        st.info(
            "ℹ️ Your uploaded file does not have repeated transactions across multiple months "
            "to establish recurring patterns. Click below to explore with simulated EMI and bill data."
        )
        if st.checkbox("✨ Preview with Simulated Monthly EMIs & Bills", value=True):
            sim_txs = generate_simulated_transactions()
            tracker = BillTracker(sim_txs, as_of_date=date(2024, 4, 1), current_balance=1500.0)

    bills = tracker.recurring_bills
    emis = tracker.get_emis()
    proj = tracker.cash_outflow_projection
    alerts = tracker.get_alerts_by_urgency()

    # Metrics
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Recurring Bills Detected", len(bills))
    m2.metric("Active EMIs / Loans", len(emis))
    m3.metric("Projected 30-Day Outflow", f"${proj.total_projected_outflow:,.2f}" if proj else "$0.00")
    m4.metric("EMI Outflow", f"${proj.total_emi_outflow:,.2f}" if proj else "$0.00")

    st.markdown("<br>", unsafe_allow_html=True)

    # Alerts Feed
    st.markdown("#### 🚨 Urgency-Sorted Priority Alerts")
    if not alerts:
        st.success("✅ No urgent payment alerts detected.")
    else:
        for a in alerts[:6]:
            if a.priority == AlertPriority.CRITICAL:
                fn = st.error
            elif a.priority == AlertPriority.HIGH:
                fn = st.warning
            else:
                fn = st.info

            emi_label = " 🏦 EMI" if a.is_emi else ""
            if a.due_date and a.days_until_due is not None:
                due_info = f" | Due: {a.due_date} ({a.days_until_due}d left)"
            elif a.due_date:
                due_info = f" | Due: {a.due_date}"
            else:
                due_info = ""

            fn(
                f"**{a.title}**{emi_label} — Score {a.urgency_score}{due_info}\n\n"
                f"{a.message}"
            )

    st.markdown("<br>", unsafe_allow_html=True)

    # Detected Bills Table
    st.markdown("#### 📋 Detected Recurring Bills & EMIs")
    if bills:
        rows = []
        for b in bills:
            rows.append({
                "Bill / Merchant": b.name,
                "Category": b.category,
                "Type": "Loan EMI 🏦" if b.is_emi else "Bill 📄",
                "Expected Outflow": f"${b.expected_amount:,.2f}",
                "Frequency": b.frequency.capitalize(),
                "Next Due Date": b.next_due_date.strftime("%Y-%m-%d"),
                "Occurrences": b.payment_count,
            })
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    else:
        st.info("No recurring bills identified.")
