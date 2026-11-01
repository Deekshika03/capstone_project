"""
src/ui/app.py — Chunk 8
Senior-Friendly FinGuard AI Dashboard with Voice Interaction.

Run with: streamlit run src/ui/app.py
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import math
from datetime import date

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

from src.ingestion.csv_parser import parse_csv
from src.ingestion.transaction import Transaction
from src.planning.bill_tracker import BillTracker
from src.planning.emergency_fund import (
    build_expense_profile,
    compute_emergency_corpus,
    analyse_fund_gap,
    generate_milestone_report,
)
from src.assistant.voice import (
    text_to_speech_html,
    build_report_speech,
    parse_voice_command,
    tts_available,
    stt_available,
)

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="FinGuard AI — Senior Dashboard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Senior-friendly CSS ───────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Base font size — larger for seniors */
    html, body, [class*="css"] { font-size: 18px !important; }

    /* High-contrast metric cards */
    .senior-card {
        background: #1a1a2e;
        border: 2px solid #4a90d9;
        border-radius: 16px;
        padding: 24px 20px;
        text-align: center;
        margin-bottom: 12px;
    }
    .senior-label {
        color: #b0c4de;
        font-size: 16px;
        font-weight: 600;
        letter-spacing: 0.5px;
        margin-bottom: 8px;
    }
    .senior-value {
        font-size: 36px;
        font-weight: 800;
        line-height: 1.1;
    }
    .green  { color: #4ade80; }
    .red    { color: #f87171; }
    .blue   { color: #60a5fa; }
    .yellow { color: #facc15; }

    /* Extra-large buttons */
    .stButton > button {
        font-size: 20px !important;
        padding: 14px 28px !important;
        border-radius: 12px !important;
        font-weight: 700 !important;
        min-height: 56px !important;
    }

    /* Larger tab labels */
    .stTabs [data-baseweb="tab"] {
        font-size: 18px !important;
        font-weight: 700 !important;
        padding: 12px 24px !important;
    }

    /* Larger input labels */
    label { font-size: 17px !important; font-weight: 600 !important; }

    /* Alert boxes */
    .alert-box {
        border-radius: 12px;
        padding: 16px 20px;
        margin: 8px 0;
        font-size: 17px;
        font-weight: 600;
    }
    .alert-critical { background: #3b1f1f; border-left: 6px solid #f87171; }
    .alert-high     { background: #3b2e1f; border-left: 6px solid #fb923c; }
    .alert-info     { background: #1f2e3b; border-left: 6px solid #60a5fa; }
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

CATEGORIES = {
    "Food":          ["grocery","restaurant","food","zomato","uber eats","starbucks","coffee","dining"],
    "Transport":     ["uber","lyft","taxi","bus","gas station","fuel","metro","cab","ride"],
    "Shopping":      ["amazon","clothing","store","shop","mall"],
    "Bills":         ["bill","electric","internet","phone","water","subscription","netflix","spotify"],
    "Entertainment": ["movie","concert","tickets","gym","gaming"],
}

def categorize(desc: str) -> str:
    d = desc.lower()
    for cat, kws in CATEGORIES.items():
        if any(k in d for k in kws):
            return cat
    return "Other"

def load_df(uploaded) -> pd.DataFrame:
    try:
        txs = parse_csv(uploaded)
    except ValueError as e:
        st.error(f"❌ {e}")
        st.stop()
    rows = []
    for t in txs:
        rows.append({
            "Date":        pd.to_datetime(str(t.date)),
            "Description": t.description,
            "Amount":      t.amount,
            "Type":        t.type,
            "Category":    t.category or categorize(t.description),
            "Month":       pd.to_datetime(str(t.date)).strftime("%b %Y"),
        })
    return pd.DataFrame(rows)

def compute_health_score(savings_rate, expense_ratio, ef_pct_3m):
    s1 = min(savings_rate / 20 * 40, 40)
    s2 = max((1 - (expense_ratio - 60) / 40) * 30, 0) if expense_ratio > 60 else 30
    s3 = min(ef_pct_3m / 100 * 30, 30)
    return round(s1 + s2 + s3)

def score_color(s):
    if s >= 80: return "#4ade80"
    if s >= 60: return "#facc15"
    if s >= 40: return "#fb923c"
    return "#f87171"

def card(col, label, value, css):
    col.markdown(f"""
    <div class="senior-card">
        <div class="senior-label">{label}</div>
        <div class="senior-value {css}">{value}</div>
    </div>""", unsafe_allow_html=True)


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Settings")
    is_senior = st.checkbox("👴 Senior Citizen Mode (60+)", value=True,
                            help="Adds 2-month medical buffer to emergency fund target.")
    current_savings = st.number_input("💰 Current Savings (₹)", min_value=0.0,
                                      value=50000.0, step=1000.0)
    monthly_contrib = st.number_input("📅 Monthly Contribution (₹)", min_value=0.0,
                                      value=3000.0, step=500.0)
    current_balance = st.number_input("🏦 Current Bank Balance (₹)", min_value=0.0,
                                      value=15000.0, step=1000.0)
    st.markdown("---")
    st.markdown("### 📖 How to Use")
    st.markdown("""
1. Upload your bank statement CSV
2. View your dashboard summary
3. Press **🔊 Read Report Aloud** to hear your summary
4. Use **🎤 Ask FinGuard** to speak a question
""")

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<h1 style='font-size:42px; font-weight:900; color:#60a5fa;'>
    🛡️ FinGuard AI — Your Financial Guardian
</h1>
<p style='font-size:20px; color:#b0c4de;'>
    Simple. Clear. Designed for you.
</p>
""", unsafe_allow_html=True)

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_upload, tab_dashboard, tab_emi, tab_fund, tab_voice = st.tabs([
    "📂 Upload",
    "📊 Dashboard",
    "💳 EMI Calendar",
    "🛡️ Emergency Fund",
    "🎤 Voice Assistant",
])

# ════════════════════════════════════════════════════════════════════════════
# TAB 1 — UPLOAD
# ════════════════════════════════════════════════════════════════════════════
with tab_upload:
    st.markdown("### 📂 Upload Your Bank Statement")
    st.markdown(
        "<p style='font-size:18px;'>Upload a CSV file with columns: "
        "<b>Date, Description, Amount, Type</b></p>",
        unsafe_allow_html=True,
    )

    uploaded = st.file_uploader(
        "Choose your CSV file", type=["csv"],
        help="Export your bank statement as CSV and upload here.",
    )

    col_dl, _ = st.columns([1, 3])
    with col_dl:
        with open("sample_transactions.csv", "rb") as f:
            st.download_button(
                "⬇️ Download Sample CSV",
                f, "sample_transactions.csv", "text/csv",
            )

    if uploaded:
        df = load_df(uploaded)
        st.session_state["df"] = df
        st.success(f"✅ Loaded **{len(df)} transactions** successfully!")
        st.dataframe(
            df[["Date", "Description", "Amount", "Type", "Category"]].head(10),
            use_container_width=True, hide_index=True,
        )
        st.caption(f"Showing first 10 of {len(df)} rows. Switch to Dashboard tab to see full analysis.")
    else:
        st.info("👆 Upload a CSV file above to get started.")
