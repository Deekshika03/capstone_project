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
        for a in alerts[:6]:  # Display top priority alerts
            badge_color = {
                AlertPriority.CRITICAL: "#ef4444",
                AlertPriority.HIGH: "#f97316",
                AlertPriority.MEDIUM: "#eab308",
                AlertPriority.LOW: "#38bdf8",
                AlertPriority.INFO: "#94a3b8",
            }.get(a.priority, "#94a3b8")

            st.markdown(
                f"""
                <div style="border-left: 4px solid {badge_color}; background: #1e1e2e; padding: 10px 14px; border-radius: 6px; margin-bottom: 8px;">
                    <div style="display:flex; justify-content:space-between;">
                        <strong style="color:#ffffff;">{a.title}</strong>
                        <span style="background:{badge_color}; color:#ffffff; padding:2px 6px; border-radius:4px; font-size:11px; font-weight:700;">
                            {a.priority.value} (Score {a.urgency_score})
                        </span>
                    </div>
                    <div style="color:#cbd5e1; font-size:13px; margin-top:4px;">{a.message}</div>
                    {f'<div style="color:#9ca3af; font-size:12px; margin-top:2px;">Due: {a.due_date} &bull; {a.days_until_due}d left</div>' if a.due_date and a.days_until_due is not None else ''}
                </div>
                """,
                unsafe_allow_html=True,
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
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("No recurring bills identified.")
