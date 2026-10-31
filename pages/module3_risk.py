import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import math

st.title("🛡️ Financial Risk Score & Emergency Fund Planner")
st.caption("Understand your financial health and plan your safety net.")

<<<<<<< HEAD
# ── Inputs ────────────────────────────────────────────────────────────────────
st.subheader("📝 Enter Your Monthly Financial Details")

c1, c2 = st.columns(2)
with c1:
    monthly_income   = st.number_input("Monthly Income ($)",           min_value=0.0, value=5000.0, step=100.0)
    essential_expenses = st.number_input("Essential Monthly Expenses ($)", min_value=0.0, value=2000.0, step=100.0,
                                         help="Rent, groceries, utilities, transport — things you must pay.")
with c2:
    current_savings  = st.number_input("Current Savings / Emergency Fund ($)", min_value=0.0, value=3000.0, step=100.0)
    emi_payments     = st.number_input("Monthly EMI / Loan Payments ($)",      min_value=0.0, value=500.0,  step=50.0)

planned_monthly_savings = st.number_input(
    "How much do you plan to save each month? ($)",
    min_value=0.0, value=500.0, step=50.0,
    help="The amount you intend to set aside every month going forward."
)

st.markdown("---")

# ── Validation ────────────────────────────────────────────────────────────────
=======
st.subheader("📝 Enter Your Monthly Financial Details")
c1, c2 = st.columns(2)
with c1:
    monthly_income     = st.number_input("Monthly Income ($)",               min_value=0.0, value=5000.0, step=100.0)
    essential_expenses = st.number_input("Essential Monthly Expenses ($)",   min_value=0.0, value=2000.0, step=100.0)
with c2:
    current_savings    = st.number_input("Current Savings ($)",              min_value=0.0, value=3000.0, step=100.0)
    emi_payments       = st.number_input("Monthly EMI / Loan Payments ($)",  min_value=0.0, value=500.0,  step=50.0)

planned_monthly_savings = st.number_input("Planned monthly savings ($)", min_value=0.0, value=500.0, step=50.0)
st.markdown("---")

>>>>>>> c9415fcb641fe73e98915560ccf32c9bbdff371b
errors = []
if monthly_income <= 0:
    errors.append("Monthly income must be greater than 0.")
if essential_expenses > monthly_income:
    errors.append("Essential expenses cannot exceed monthly income.")
if emi_payments > monthly_income:
    errors.append("EMI payments cannot exceed monthly income.")
if essential_expenses + emi_payments > monthly_income:
<<<<<<< HEAD
    errors.append("Combined essential expenses and EMIs exceed your income — no room to save.")
=======
    errors.append("Combined essential expenses and EMIs exceed your income.")
>>>>>>> c9415fcb641fe73e98915560ccf32c9bbdff371b

if errors:
    for e in errors:
        st.error(f"❌ {e}")
    st.stop()

<<<<<<< HEAD
# ── Core Calculations ─────────────────────────────────────────────────────────
total_outflow    = essential_expenses + emi_payments
monthly_savings  = monthly_income - total_outflow
savings_rate     = (monthly_savings / monthly_income) * 100          # %
expense_ratio    = (total_outflow / monthly_income) * 100            # %

# Emergency fund: 3–6 months of essential expenses
=======
total_outflow  = essential_expenses + emi_payments
monthly_savings = monthly_income - total_outflow
savings_rate   = (monthly_savings / monthly_income) * 100
expense_ratio  = (total_outflow / monthly_income) * 100

>>>>>>> c9415fcb641fe73e98915560ccf32c9bbdff371b
ef_target_3m = essential_expenses * 3
ef_target_6m = essential_expenses * 6
ef_pct_3m    = min((current_savings / ef_target_3m) * 100, 100) if ef_target_3m > 0 else 100
ef_pct_6m    = min((current_savings / ef_target_6m) * 100, 100) if ef_target_6m > 0 else 100
<<<<<<< HEAD

remaining_3m = max(ef_target_3m - current_savings, 0)
remaining_6m = max(ef_target_6m - current_savings, 0)

months_to_3m = math.ceil(remaining_3m / planned_monthly_savings) if planned_monthly_savings > 0 and remaining_3m > 0 else 0
months_to_6m = math.ceil(remaining_6m / planned_monthly_savings) if planned_monthly_savings > 0 and remaining_6m > 0 else 0

# ── Financial Health Score (out of 100) ───────────────────────────────────────
# Component 1 — Savings rate (40 pts): 20%+ savings rate = full marks
score_savings = min(savings_rate / 20 * 40, 40)

# Component 2 — Expense ratio (30 pts): below 60% expense ratio = full marks
score_expense = max((1 - (expense_ratio - 60) / 40) * 30, 0) if expense_ratio > 60 else 30

# Component 3 — Emergency fund (30 pts): reaching 3-month target = full marks
score_ef = min(ef_pct_3m / 100 * 30, 30)

health_score = round(score_savings + score_expense + score_ef)
=======
remaining_3m = max(ef_target_3m - current_savings, 0)
remaining_6m = max(ef_target_6m - current_savings, 0)
months_to_3m = math.ceil(remaining_3m / planned_monthly_savings) if planned_monthly_savings > 0 and remaining_3m > 0 else 0
months_to_6m = math.ceil(remaining_6m / planned_monthly_savings) if planned_monthly_savings > 0 and remaining_6m > 0 else 0

score_savings = min(savings_rate / 20 * 40, 40)
score_expense = max((1 - (expense_ratio - 60) / 40) * 30, 0) if expense_ratio > 60 else 30
score_ef      = min(ef_pct_3m / 100 * 30, 30)
health_score  = round(score_savings + score_expense + score_ef)
>>>>>>> c9415fcb641fe73e98915560ccf32c9bbdff371b

def score_label(s):
    if s >= 80: return "Excellent 🟢", "#4ade80"
    if s >= 60: return "Good 🟡",      "#facc15"
    if s >= 40: return "Fair 🟠",      "#fb923c"
    return "Needs Attention 🔴",       "#f87171"

label, color = score_label(health_score)

<<<<<<< HEAD
# ── Score Gauge ───────────────────────────────────────────────────────────────
st.subheader("📊 Financial Health Score")

=======
st.subheader("📊 Financial Health Score")
>>>>>>> c9415fcb641fe73e98915560ccf32c9bbdff371b
gauge = go.Figure(go.Indicator(
    mode="gauge+number",
    value=health_score,
    number={"suffix": "/100", "font": {"size": 36, "color": color}},
    gauge={
<<<<<<< HEAD
        "axis": {"range": [0, 100], "tickwidth": 1},
=======
        "axis": {"range": [0, 100]},
>>>>>>> c9415fcb641fe73e98915560ccf32c9bbdff371b
        "bar":  {"color": color},
        "steps": [
            {"range": [0,  40], "color": "#3b1f1f"},
            {"range": [40, 60], "color": "#3b2e1f"},
            {"range": [60, 80], "color": "#2e3b1f"},
            {"range": [80,100], "color": "#1f3b2a"},
        ],
<<<<<<< HEAD
        "threshold": {"line": {"color": "white", "width": 3}, "thickness": 0.75, "value": health_score},
=======
>>>>>>> c9415fcb641fe73e98915560ccf32c9bbdff371b
    },
    title={"text": f"<b>{label}</b>", "font": {"size": 18}},
))
gauge.update_layout(height=280, margin=dict(t=30, b=10, l=20, r=20),
                    paper_bgcolor="rgba(0,0,0,0)", font_color="white")
st.plotly_chart(gauge, use_container_width=True)

<<<<<<< HEAD
# ── Score Breakdown ───────────────────────────────────────────────────────────
st.subheader("🔍 Score Breakdown")
b1, b2, b3 = st.columns(3)
for col, title, pts, max_pts, detail in [
    (b1, "Savings Rate",    score_savings, 40, f"{savings_rate:.1f}% of income saved"),
    (b2, "Expense Ratio",   score_expense, 30, f"{expense_ratio:.1f}% of income spent"),
    (b3, "Emergency Fund",  score_ef,      30, f"{ef_pct_3m:.1f}% of 3-month target"),
=======
st.subheader("🔍 Score Breakdown")
b1, b2, b3 = st.columns(3)
for col, title, pts, max_pts, detail in [
    (b1, "Savings Rate",   score_savings, 40, f"{savings_rate:.1f}% of income saved"),
    (b2, "Expense Ratio",  score_expense, 30, f"{expense_ratio:.1f}% of income spent"),
    (b3, "Emergency Fund", score_ef,      30, f"{ef_pct_3m:.1f}% of 3-month target"),
>>>>>>> c9415fcb641fe73e98915560ccf32c9bbdff371b
]:
    col.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">{title}</div>
        <div class="metric-value score">{pts:.0f}<span style="font-size:16px;color:#a0a0c0">/{max_pts}</span></div>
        <div class="metric-label">{detail}</div>
    </div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

<<<<<<< HEAD
# ── Monthly Cash Flow ─────────────────────────────────────────────────────────
st.subheader("💵 Monthly Cash Flow")
m1, m2, m3 = st.columns(3)
for col, lbl, val, css in [
    (m1, "Monthly Savings",  f"${monthly_savings:,.2f}",  "income"),
    (m2, "Savings Rate",     f"{savings_rate:.1f}%",      "balance"),
    (m3, "Expense Ratio",    f"{expense_ratio:.1f}%",     "expense"),
=======
st.subheader("💵 Monthly Cash Flow")
m1, m2, m3 = st.columns(3)
for col, lbl, val, css in [
    (m1, "Monthly Savings", f"${monthly_savings:,.2f}", "income"),
    (m2, "Savings Rate",    f"{savings_rate:.1f}%",     "balance"),
    (m3, "Expense Ratio",   f"{expense_ratio:.1f}%",    "expense"),
>>>>>>> c9415fcb641fe73e98915560ccf32c9bbdff371b
]:
    col.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">{lbl}</div>
        <div class="metric-value {css}">{val}</div>
    </div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

<<<<<<< HEAD
# ── Emergency Fund Progress ───────────────────────────────────────────────────
st.subheader("🏦 Emergency Fund Progress")

=======
st.subheader("🏦 Emergency Fund Progress")
>>>>>>> c9415fcb641fe73e98915560ccf32c9bbdff371b
ef1, ef2 = st.columns(2)
with ef1:
    st.markdown("**3-Month Target**")
    st.progress(int(ef_pct_3m))
    st.caption(f"${current_savings:,.2f} of ${ef_target_3m:,.2f} ({ef_pct_3m:.1f}%)")
    if remaining_3m > 0:
        st.caption(f"Still need: **${remaining_3m:,.2f}**")
        if months_to_3m > 0:
<<<<<<< HEAD
            st.caption(f"At ${planned_monthly_savings:,.0f}/month → **{months_to_3m} months** to reach target")
=======
            st.caption(f"At ${planned_monthly_savings:,.0f}/month → **{months_to_3m} months**")
>>>>>>> c9415fcb641fe73e98915560ccf32c9bbdff371b
    else:
        st.success("✅ 3-month target reached!")

with ef2:
    st.markdown("**6-Month Target (Ideal)**")
    st.progress(int(ef_pct_6m))
    st.caption(f"${current_savings:,.2f} of ${ef_target_6m:,.2f} ({ef_pct_6m:.1f}%)")
    if remaining_6m > 0:
        st.caption(f"Still need: **${remaining_6m:,.2f}**")
        if months_to_6m > 0:
<<<<<<< HEAD
            st.caption(f"At ${planned_monthly_savings:,.0f}/month → **{months_to_6m} months** to reach target")
=======
            st.caption(f"At ${planned_monthly_savings:,.0f}/month → **{months_to_6m} months**")
>>>>>>> c9415fcb641fe73e98915560ccf32c9bbdff371b
    else:
        st.success("✅ 6-month target reached!")

st.markdown("<br>", unsafe_allow_html=True)

<<<<<<< HEAD
# ── Savings Growth Projection Chart ──────────────────────────────────────────
st.subheader("📈 Savings Growth Projection (12 Months)")

=======
st.subheader("📈 Savings Growth Projection (12 Months)")
>>>>>>> c9415fcb641fe73e98915560ccf32c9bbdff371b
if planned_monthly_savings > 0:
    months = list(range(0, 13))
    projected = [current_savings + planned_monthly_savings * m for m in months]
    proj_df = pd.DataFrame({"Month": months, "Projected Savings": projected})
<<<<<<< HEAD

=======
>>>>>>> c9415fcb641fe73e98915560ccf32c9bbdff371b
    fig_proj = px.line(proj_df, x="Month", y="Projected Savings", markers=True,
                       color_discrete_sequence=["#60a5fa"])
    fig_proj.add_hline(y=ef_target_3m, line_dash="dash", line_color="#4ade80",
                       annotation_text="3-Month Target", annotation_position="bottom right")
    fig_proj.add_hline(y=ef_target_6m, line_dash="dash", line_color="#facc15",
                       annotation_text="6-Month Target", annotation_position="bottom right")
    fig_proj.update_layout(margin=dict(t=10, b=10), paper_bgcolor="rgba(0,0,0,0)",
                           font_color="white", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig_proj, use_container_width=True)
else:
    st.info("Enter a planned monthly savings amount to see the projection chart.")

<<<<<<< HEAD
# ── Personalized Suggestions ──────────────────────────────────────────────────
st.subheader("💡 Personalized Suggestions")

suggestions = []

if savings_rate < 10:
    suggestions.append("🔴 Your savings rate is below 10%. Try to save at least 20% of your income each month.")
elif savings_rate < 20:
    suggestions.append("🟡 Your savings rate is between 10–20%. Aim to push it above 20% by trimming discretionary spending.")
else:
    suggestions.append("🟢 Great savings rate! Keep it up and consider investing the surplus.")

if expense_ratio > 80:
    suggestions.append("🔴 Over 80% of your income goes to expenses. Look for areas to cut — subscriptions, dining out, or shopping.")
elif expense_ratio > 60:
    suggestions.append("🟡 Expense ratio is moderate. Review non-essential expenses to free up more savings.")

if emi_payments > monthly_income * 0.3:
    suggestions.append("🔴 EMI payments exceed 30% of income. Consider prepaying loans or refinancing to reduce the burden.")

if ef_pct_3m < 50:
    suggestions.append(f"🔴 Emergency fund is less than half of the 3-month target. Prioritize building it to ${ef_target_3m:,.0f}.")
elif ef_pct_3m < 100:
    suggestions.append(f"🟡 You're on your way to the 3-month emergency fund. Keep saving ${planned_monthly_savings:,.0f}/month.")

if health_score >= 80:
    suggestions.append("🌟 Excellent financial health! Consider diversifying into investments like index funds or SIPs.")

=======
st.subheader("💡 Personalized Suggestions")
suggestions = []
if savings_rate < 10:
    suggestions.append("🔴 Savings rate below 10%. Aim for at least 20% of income.")
elif savings_rate < 20:
    suggestions.append("🟡 Savings rate 10–20%. Push above 20% by trimming discretionary spending.")
else:
    suggestions.append("🟢 Great savings rate! Consider investing the surplus.")
if expense_ratio > 80:
    suggestions.append("🔴 Over 80% of income goes to expenses. Review subscriptions, dining, and shopping.")
elif expense_ratio > 60:
    suggestions.append("🟡 Moderate expense ratio. Look for non-essentials to cut.")
if emi_payments > monthly_income * 0.3:
    suggestions.append("🔴 EMIs exceed 30% of income. Consider prepaying or refinancing loans.")
if ef_pct_3m < 50:
    suggestions.append(f"🔴 Emergency fund is under 50% of the 3-month target. Prioritize building it to ${ef_target_3m:,.0f}.")
elif ef_pct_3m < 100:
    suggestions.append(f"🟡 Keep saving ${planned_monthly_savings:,.0f}/month to reach your emergency fund goal.")
if health_score >= 80:
    suggestions.append("🌟 Excellent financial health! Consider diversifying into index funds or SIPs.")
>>>>>>> c9415fcb641fe73e98915560ccf32c9bbdff371b
for s in suggestions:
    st.markdown(f"- {s}")
