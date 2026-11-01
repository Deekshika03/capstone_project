import calendar
from datetime import date, datetime, timedelta
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.ingestion.csv_parser import parse_csv
from src.planning.bill_tracker import (
    AlertPriority,
    BillTracker,
    generate_simulated_transactions,
)

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="FinGuard AI – Recurring Bills & EMI Detector",
    page_icon="💳",
    layout="wide",
)

# ── Styling ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #1e1e2e, #2a2a3e);
        border-radius: 12px;
        padding: 18px;
        text-align: center;
        border: 1px solid #3a3a5e;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
    }
    .metric-label { color: #a0a0c0; font-size: 13px; font-weight: 500; margin-bottom: 6px; }
    .metric-value { font-size: 26px; font-weight: 700; }
    .income  { color: #4ade80; }
    .expense { color: #f87171; }
    .balance { color: #60a5fa; }
    .warning { color: #fbbf24; }
    
    .alert-card-critical {
        background: linear-gradient(135deg, #381212, #240a0a);
        border-left: 5px solid #ef4444;
        border-radius: 8px;
        padding: 14px 18px;
        margin-bottom: 12px;
    }
    .alert-card-high {
        background: linear-gradient(135deg, #3b2210, #26150a);
        border-left: 5px solid #f97316;
        border-radius: 8px;
        padding: 14px 18px;
        margin-bottom: 12px;
    }
    .alert-card-medium {
        background: linear-gradient(135deg, #352d12, #211c09);
        border-left: 5px solid #eab308;
        border-radius: 8px;
        padding: 14px 18px;
        margin-bottom: 12px;
    }
    .alert-card-low {
        background: linear-gradient(135deg, #10243b, #091524);
        border-left: 5px solid #38bdf8;
        border-radius: 8px;
        padding: 14px 18px;
        margin-bottom: 12px;
    }
    .badge {
        display: inline-block;
        padding: 3px 8px;
        border-radius: 6px;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.5px;
        text-transform: uppercase;
    }
    .badge-critical { background: #ef4444; color: #ffffff; }
    .badge-high     { background: #f97316; color: #ffffff; }
    .badge-medium   { background: #eab308; color: #1e1e2e; }
    .badge-low      { background: #38bdf8; color: #0f172a; }
    .badge-emi      { background: #8b5cf6; color: #ffffff; }
</style>
""", unsafe_allow_html=True)

# ── Title & Caption ───────────────────────────────────────────────────────────
st.title("💳 Recurring Bills & EMI Detector")
st.caption("Module 4: Identify recurring transactions, project 30-day cash outflows, and receive urgency-ranked priority alerts.")

# ── Sidebar Controls ──────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Simulation & Budget Settings")
    
    current_balance = st.number_input(
        "Current Bank Balance ($)",
        min_value=0.0,
        value=1500.0,
        step=100.0,
        help="Used to test insufficient balance alerts when upcoming EMIs/bills are due.",
    )
    
    as_of_date_input = st.date_input(
        "Reference 'As of' Date",
        value=date(2024, 4, 1),
        help="The projection anchor date from which the next 30 days are evaluated.",
    )

    amount_tolerance = st.slider(
        "Amount Variation Tolerance",
        min_value=0.01,
        max_value=0.30,
        value=0.15,
        step=0.01,
        help="Tolerance for slight bill amount fluctuations (e.g. utilities).",
    )

# ── Tabs for Data Source ──────────────────────────────────────────────────────
tab_sim, tab_upload = st.tabs(["✨ Simulated Monthly EMIs & Bills (Demo)", "📂 Upload Your Statement (CSV)"])

transactions_data = None

with tab_sim:
    st.markdown("""
    This demo uses simulated multi-month bank transactions featuring:
    - **Home Loan EMI** ($1,250.00 on the 5th)
    - **Car Loan EMI** ($380.00 on the 10th)
    - **Apartment Rent** ($1,400.00 on the 1st)
    - **Health Insurance Premium** ($210.00 on the 15th)
    - **Utility Bills** (Electricity ~$111 on 18th, Internet $60 on 12th)
    - **Netflix Subscription** ($15.99 on the 8th)
    """)
    transactions_data = generate_simulated_transactions()

with tab_upload:
    uploaded_file = st.file_uploader(
        "Upload bank transactions CSV (Date, Description, Amount, Type)",
        type="csv",
        key="bills_csv_upload",
    )
    if uploaded_file is not None:
        try:
            parsed = parse_csv(uploaded_file)
            transactions_data = parsed
            st.success(f"Loaded {len(parsed)} transactions from uploaded CSV.")
        except Exception as e:
            st.error(f"Failed to parse CSV: {e}")

if not transactions_data:
    st.info("No transaction data loaded. Please select simulated data or upload a CSV file.")
    st.stop()

# ── Run Detection & Projection Engine ─────────────────────────────────────────
tracker = BillTracker(
    transactions=transactions_data,
    as_of_date=as_of_date_input,
    current_balance=current_balance,
    amount_tolerance=amount_tolerance,
    min_occurrences=2,
)

projection = tracker.cash_outflow_projection
alerts = tracker.get_alerts_by_urgency()
bills = tracker.recurring_bills
emis = tracker.get_emis()

# ── Top Summary Metrics ───────────────────────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)
col1, col2, col3, col4 = st.columns(4)

projected_end_balance = current_balance - (projection.total_projected_outflow if projection else 0)

with col1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Current Cash Balance</div>
        <div class="metric-value balance">${current_balance:,.2f}</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Projected 30-Day Outflow</div>
        <div class="metric-value expense">${projection.total_projected_outflow:,.2f}</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Upcoming EMI Outflows</div>
        <div class="metric-value warning">${projection.total_emi_outflow:,.2f}</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    end_color = "income" if projected_end_balance >= 0 else "expense"
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Net Projected Balance (30 Days)</div>
        <div class="metric-value {end_color}">${projected_end_balance:,.2f}</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Priority Alerts Feed ──────────────────────────────────────────────────────
st.subheader("🚨 Priority Payment Alerts (Sorted by Urgency)")

if not alerts:
    st.success("✅ No urgent payment alerts detected. All projected cash flows are balanced!")
else:
    for a in alerts:
        # Choose native Streamlit alert based on priority
        if a.priority == AlertPriority.CRITICAL:
            fn = st.error
        elif a.priority == AlertPriority.HIGH:
            fn = st.warning
        elif a.priority == AlertPriority.MEDIUM:
            fn = st.info
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

# ── Charts: 30-Day Cash Outflow Projection ─────────────────────────────────────
st.subheader("📈 Projected 30-Day Cash Outflows")

chart_col1, chart_col2 = st.columns(2)

upcoming_list = projection.upcoming_payments if projection else []

if upcoming_list:
    proj_rows = []
    running_b = current_balance
    for p in sorted(upcoming_list, key=lambda x: x.due_date):
        running_b -= p.amount
        proj_rows.append({
            "Due Date": p.due_date.isoformat(),
            "Bill Name": p.bill_name,
            "Amount": p.amount,
            "Category": p.category,
            "Is EMI": "EMI" if p.is_emi else "Bill",
            "Projected Balance": running_b,
        })
    df_proj = pd.DataFrame(proj_rows)

    with chart_col1:
        st.markdown("**Upcoming Bills by Due Date**")
        fig_bar = px.bar(
            df_proj,
            x="Due Date",
            y="Amount",
            color="Category",
            hover_data=["Bill Name", "Is EMI"],
            labels={"Amount": "Outflow ($)", "Due Date": "Date"},
            color_discrete_sequence=px.colors.qualitative.Pastel,
        )
        fig_bar.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="#ffffff",
            margin=dict(t=20, b=20, l=10, r=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    with chart_col2:
        st.markdown("**Projected Cash Balance Trajectory**")
        fig_line = px.line(
            df_proj,
            x="Due Date",
            y="Projected Balance",
            markers=True,
            labels={"Projected Balance": "Balance ($)", "Due Date": "Date"},
            color_discrete_sequence=["#60a5fa"],
        )
        fig_line.add_hline(
            y=0,
            line_dash="dash",
            line_color="#ef4444",
            annotation_text="Zero Balance Line",
            annotation_position="bottom right",
        )
        fig_line.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="#ffffff",
            margin=dict(t=20, b=20, l=10, r=10),
        )
        st.plotly_chart(fig_line, use_container_width=True)
else:
    st.info("No upcoming payments within the next 30-day projection window.")

st.markdown("<br>", unsafe_allow_html=True)

# ── Detected Recurring Bills & EMIs Table ──────────────────────────────────────
st.subheader("📋 Detected Recurring Bills & EMIs")

if not bills:
    st.info("No recurring patterns detected. Ensure at least 2 consecutive occurrences are present.")
else:
    table_rows = []
    for b in bills:
        table_rows.append({
            "Bill / Merchant": b.name,
            "Category": b.category,
            "Type": "Loan EMI 🏦" if b.is_emi else "Bill 📄",
            "Expected Amount ($)": f"${b.expected_amount:,.2f}",
            "Frequency": b.frequency.capitalize(),
            "Avg Interval (Days)": b.interval_days,
            "Last Paid": b.last_payment_date.strftime("%Y-%m-%d"),
            "Next Due Date": b.next_due_date.strftime("%Y-%m-%d"),
            "Historical Payments": b.payment_count,
            "Confidence": f"{int(b.confidence_score * 100)}%",
        })
    df_bills = pd.DataFrame(table_rows)

    tab_all, tab_emis_only = st.tabs(["All Detected Recurring Bills", f"EMIs Only ({len(emis)})"])
    with tab_all:
        st.dataframe(df_bills, use_container_width=True, hide_index=True)
    with tab_emis_only:
        df_emis = df_bills[df_bills["Type"].str.contains("EMI")]
        st.dataframe(df_emis, use_container_width=True, hide_index=True)

# ── Upcoming 30-Day Payment Schedule ──────────────────────────────────────────
st.subheader("🗓️ Detailed 30-Day Outflow Schedule")

if upcoming_list:
    sched_rows = []
    for p in upcoming_list:
        sched_rows.append({
            "Due Date": p.due_date.strftime("%Y-%m-%d"),
            "Days Left": p.days_until_due,
            "Bill Name": p.bill_name,
            "Category": p.category,
            "Amount ($)": f"${p.amount:,.2f}",
            "Type": "EMI 🏦" if p.is_emi else "Bill 📄",
            "Urgency Status": p.urgency_status,
        })
    df_sched = pd.DataFrame(sched_rows)
    st.dataframe(df_sched, use_container_width=True, hide_index=True)
else:
    st.info("No payments due in the next 30 days.")
