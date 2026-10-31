import streamlit as st
import pandas as pd
import plotly.express as px
from PIL import Image

from src.ingestion.csv_parser import parse_csv
from src.ingestion.ocr_parser import parse_image, parse_image_raw_text
from src.ingestion.transaction import Transaction

CATEGORIES = {
    "Food":          ["grocery", "restaurant", "food", "zomato", "uber eats", "starbucks", "coffee", "dining"],
    "Transport":     ["uber", "lyft", "taxi", "bus", "gas station", "fuel", "metro", "cab", "ride"],
    "Shopping":      ["amazon", "clothing", "store", "shop", "mall"],
    "Bills":         ["bill", "electric", "internet", "phone", "water", "subscription", "netflix", "spotify"],
    "Entertainment": ["movie", "concert", "tickets", "gym", "gaming"],
}

def categorize(description: str) -> str:
    desc = description.lower()
    for category, keywords in CATEGORIES.items():
        if any(kw in desc for kw in keywords):
            return category
    return "Other"

def transactions_to_df(transactions: list[Transaction]) -> pd.DataFrame:
    rows = []
    for t in transactions:
        rows.append({
            "Date":        t.date,
            "Description": t.description,
            "Amount":      t.amount,
            "Type":        t.type,
            "Category":    categorize(t.description),
            "Month":       pd.to_datetime(str(t.date)).strftime("%b %Y"),
            "Source":      t.source or "csv",
        })
    return pd.DataFrame(rows)

st.title("💰 Smart Expense Manager")
st.caption("Upload bank transactions via CSV or scan a receipt/bill image.")

tab_csv, tab_ocr = st.tabs(["📄 Upload CSV", "🖼️ Scan Receipt / Bill"])
df = pd.DataFrame()

with tab_csv:
    uploaded = st.file_uploader("Upload CSV (Date, Description, Amount, Type)", type="csv")
    if not uploaded:
        st.info("👆 Upload a CSV to get started.")
        with open("sample_transactions.csv", "rb") as f:
            st.download_button("⬇️ Download Sample CSV", f, "sample_transactions.csv", "text/csv")
    else:
        try:
            transactions = parse_csv(uploaded)
            df = transactions_to_df(transactions)
            st.success(f"✅ Loaded {len(df)} transactions from CSV.")
        except ValueError as e:
            st.error(f"❌ {e}")

with tab_ocr:
    st.caption("Upload a photo of a receipt or bill. Supported: JPG, PNG, WEBP.")
    img_file = st.file_uploader("Upload receipt image", type=["jpg", "jpeg", "png", "webp"], key="ocr_upload")
    if img_file:
        image = Image.open(img_file)
        col_img, col_result = st.columns(2)
        with col_img:
            st.image(image, caption="Uploaded Image", use_container_width=True)
        with col_result:
            with st.spinner("Running OCR..."):
                try:
                    transactions = parse_image(image)
                    ocr_df = transactions_to_df(transactions)
                    st.success("✅ Extracted transaction:")
                    st.dataframe(ocr_df[["Date", "Description", "Amount", "Type"]], hide_index=True)
                    df = pd.concat([df, ocr_df], ignore_index=True) if not df.empty else ocr_df
                except ValueError as e:
                    st.error(f"❌ {e}")
        with st.expander("🔍 View raw OCR text"):
            st.text(parse_image_raw_text(image))

if df.empty:
    st.stop()

df["Date"] = pd.to_datetime(df["Date"])
income_df  = df[df["Type"].str.lower() == "income"]
expense_df = df[df["Type"].str.lower() == "expense"]
total_income  = income_df["Amount"].sum()
total_expense = abs(expense_df["Amount"].sum())
balance       = total_income - total_expense

st.markdown("---")
c1, c2, c3 = st.columns(3)
for col, label, value, css in [
    (c1, "Total Income",   f"${total_income:,.2f}",  "income"),
    (c2, "Total Expenses", f"${total_expense:,.2f}", "expense"),
    (c3, "Balance",        f"${balance:,.2f}",       "balance"),
]:
    col.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">{label}</div>
        <div class="metric-value {css}">{value}</div>
    </div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

col_pie, col_bar = st.columns(2)
with col_pie:
    st.subheader("🍕 Expenses by Category")
    cat_data = expense_df.groupby("Category")["Amount"].apply(lambda x: abs(x).sum()).reset_index()
    cat_data.columns = ["Category", "Amount"]
    fig_pie = px.pie(cat_data, values="Amount", names="Category",
                     color_discrete_sequence=px.colors.qualitative.Pastel, hole=0.4)
    fig_pie.update_traces(textposition="inside", textinfo="percent+label")
    fig_pie.update_layout(showlegend=False, margin=dict(t=10, b=10))
    st.plotly_chart(fig_pie, use_container_width=True)

with col_bar:
    st.subheader("📊 Monthly Income vs Expenses")
    monthly_income  = income_df.groupby("Month")["Amount"].sum().reset_index()
    monthly_expense = expense_df.groupby("Month")["Amount"].apply(lambda x: abs(x).sum()).reset_index()
    monthly_income["Type"]  = "Income"
    monthly_expense["Type"] = "Expense"
    monthly = pd.concat([monthly_income, monthly_expense])
    month_order = df.sort_values("Date")["Month"].unique().tolist()
    monthly["Month"] = pd.Categorical(monthly["Month"], categories=month_order, ordered=True)
    monthly.sort_values("Month", inplace=True)
    fig_bar = px.bar(monthly, x="Month", y="Amount", color="Type", barmode="group",
                     color_discrete_map={"Income": "#4ade80", "Expense": "#f87171"})
    fig_bar.update_layout(legend_title_text="", margin=dict(t=10, b=10))
    st.plotly_chart(fig_bar, use_container_width=True)

st.subheader("🔍 All Transactions")
search = st.text_input("Search by description or category", placeholder="e.g. Amazon, Food…")
display_df = df.copy()
if search:
    mask = (display_df["Description"].str.contains(search, case=False, na=False) |
            display_df["Category"].str.contains(search, case=False, na=False))
    display_df = display_df[mask]

display_df["Date"] = display_df["Date"].dt.strftime("%Y-%m-%d")
st.dataframe(display_df[["Date", "Description", "Amount", "Type", "Category", "Source"]],
             use_container_width=True, hide_index=True)
st.caption(f"Showing {len(display_df)} of {len(df)} transactions")
