import streamlit as st

st.set_page_config(page_title="FinGuard AI", page_icon="💰", layout="wide")

# Shared CSS used across all pages
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #1e1e2e, #2a2a3e);
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        border: 1px solid #3a3a5e;
    }
    .metric-label { color: #a0a0c0; font-size: 14px; margin-bottom: 6px; }
    .metric-value { font-size: 28px; font-weight: 700; }
    .income      { color: #4ade80; }
    .expense     { color: #f87171; }
    .balance     { color: #60a5fa; }
    .score       { color: #facc15; }
</style>
""", unsafe_allow_html=True)

pages = [
    st.Page("pages/module1_expenses.py",  title="💰 Expense Manager",       default=True),
    st.Page("pages/module2_budget.py",    title="📋 Budget Planner"),
    st.Page("pages/module3_risk.py",      title="🛡️ Risk Score & Emergency Fund"),
]

pg = st.navigation(pages)
pg.run()
