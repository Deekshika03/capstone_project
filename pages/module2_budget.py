import streamlit as st
import plotly.express as px
import pandas as pd

st.title("📋 Budget Planner")
st.caption("Set monthly budgets per category and track your spending.")

CATEGORIES = ["Food", "Transport", "Shopping", "Bills", "Entertainment", "Other"]

st.subheader("💵 Set Your Monthly Budgets")
budgets = {}
cols = st.columns(3)
for i, cat in enumerate(CATEGORIES):
    with cols[i % 3]:
        budgets[cat] = st.number_input(f"{cat} ($)", min_value=0.0, value=200.0, step=10.0, key=f"budget_{cat}")

st.subheader("📥 Enter Actual Spending")
actuals = {}
cols2 = st.columns(3)
for i, cat in enumerate(CATEGORIES):
    with cols2[i % 3]:
        actuals[cat] = st.number_input(f"{cat} ($)", min_value=0.0, value=0.0, step=10.0, key=f"actual_{cat}")

st.markdown("<br>", unsafe_allow_html=True)

data = pd.DataFrame({
    "Category": CATEGORIES,
    "Budget":   [budgets[c] for c in CATEGORIES],
    "Spent":    [actuals[c] for c in CATEGORIES],
})
data["Remaining"] = data["Budget"] - data["Spent"]
data["Status"]    = data["Remaining"].apply(lambda x: "Over Budget 🔴" if x < 0 else "On Track 🟢")

over = data[data["Remaining"] < 0]
if not over.empty:
    for _, row in over.iterrows():
        st.error(f"🚨 **{row['Category']}**: Over budget by ${abs(row['Remaining']):,.2f}")
else:
    st.success("✅ All categories are within budget!")

st.markdown("<br>", unsafe_allow_html=True)

melted = data.melt(id_vars="Category", value_vars=["Budget", "Spent"], var_name="Type", value_name="Amount")
fig = px.bar(melted, x="Category", y="Amount", color="Type", barmode="group",
             color_discrete_map={"Budget": "#60a5fa", "Spent": "#f87171"})
fig.update_layout(legend_title_text="", margin=dict(t=10, b=10))
st.plotly_chart(fig, width="stretch")

st.subheader("📊 Budget Summary")
st.dataframe(data[["Category", "Budget", "Spent", "Remaining", "Status"]],
             width="stretch", hide_index=True)

st.subheader("💡 Suggestions")
total_budget = data["Budget"].sum()
total_spent  = data["Spent"].sum()
if total_budget > 0:
    usage_pct = (total_spent / total_budget) * 100
    if usage_pct > 90:
        st.warning(f"⚠️ You've used {usage_pct:.1f}% of your total budget. Consider cutting discretionary spending.")
    elif usage_pct > 75:
        st.info(f"ℹ️ You've used {usage_pct:.1f}% of your total budget. Keep an eye on spending.")
    else:
        st.success(f"🎉 Great job! You've only used {usage_pct:.1f}% of your total budget.")

for _, row in over.iterrows():
    st.markdown(f"- Reduce **{row['Category']}** spending by at least ${abs(row['Remaining']):,.2f} next month.")
