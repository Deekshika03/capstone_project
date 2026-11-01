import streamlit as st
import pandas as pd
import plotly.express as px
from modules import budget_insights, bill_insights, emergency_fund_insights
from src.assistant.financial_assistant import generate_response, SUGGESTED_QUESTIONS, WELCOME_MESSAGE
from src.assistant.voice import text_to_speech_html, speech_to_text_from_bytes, tts_available, stt_available

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="FinGuard AI – Expense Manager", page_icon="💰", layout="wide")

# ── Styling ───────────────────────────────────────────────────────────────────
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
    .income  { color: #4ade80; }
    .expense { color: #f87171; }
    .balance { color: #60a5fa; }
    .ai-card {
        background: linear-gradient(135deg, #1a1a3e, #2d1b69);
        border-radius: 16px;
        padding: 24px;
        border: 1px solid #7c3aed;
        margin-bottom: 20px;
    }
    .ai-title { font-size: 22px; font-weight: 700; color: #c4b5fd; margin-bottom: 4px; }
    .ai-subtitle { color: #a0a0c0; font-size: 14px; margin-bottom: 16px; }
    .chat-user { background: #2d1b69; border-radius: 12px; padding: 10px 14px; margin: 6px 0; color: #e2e8f0; }
    .chat-bot  { background: #1e3a5f; border-radius: 12px; padding: 10px 14px; margin: 6px 0; color: #e2e8f0; }
</style>
""", unsafe_allow_html=True)

# ── Category keywords ─────────────────────────────────────────────────────────
CATEGORIES = {
    "Food":          ["grocery", "restaurant", "food", "zomato", "uber eats", "starbucks", "coffee", "dining"],
    "Transport":     ["uber", "lyft", "taxi", "bus", "gas station", "fuel", "metro", "cab", "ride"],
    "Shopping":      ["amazon", "clothing", "store", "shop", "mall"],
    "Bills":         ["bill", "electric", "internet", "phone", "water", "subscription", "netflix", "spotify"],
    "Entertainment": ["movie", "concert", "tickets", "gym", "gaming"],
}

def categorize(description: str) -> str:
    """Return a category based on keywords found in the transaction description."""
    desc = description.lower()
    for category, keywords in CATEGORIES.items():
        if any(kw in desc for kw in keywords):
            return category
    return "Other"

def load_and_validate(file) -> pd.DataFrame:
    """Load CSV, validate required columns, and return a clean DataFrame."""
    df = pd.read_csv(file)

    required = {"Date", "Description", "Amount", "Type"}
    missing = required - set(df.columns)
    if missing:
        st.error(f"❌ Missing columns: {', '.join(missing)}. Please check your CSV.")
        st.stop()

    # Drop rows where critical fields are empty
    df.dropna(subset=["Date", "Amount", "Type"], inplace=True)

    # Convert and validate Amount
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
    invalid = df["Amount"].isna().sum()
    if invalid:
        st.warning(f"⚠️ {invalid} row(s) had non-numeric amounts and were removed.")
    df.dropna(subset=["Amount"], inplace=True)

    # Parse dates
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df.dropna(subset=["Date"], inplace=True)

    df["Description"] = df["Description"].fillna("Unknown")
    df["Category"] = df["Description"].apply(categorize)
    df["Month"] = df["Date"].dt.strftime("%b %Y")

    return df

# ── Header ────────────────────────────────────────────────────────────────────
st.title("💰 FinGuard AI — Smart Expense Manager")
st.caption("Upload your bank transactions CSV to get instant insights.")

# ── File upload ───────────────────────────────────────────────────────────────
uploaded = st.file_uploader("📂 Upload CSV (Date, Description, Amount, Type)", type="csv")

if not uploaded:
    st.info("👆 Upload a CSV file to get started. Download the sample below to try it out.")
    with open("sample_transactions.csv", "rb") as f:
        st.download_button("⬇️ Download Sample CSV", f, "sample_transactions.csv", "text/csv")
    st.stop()

# ── Load data ─────────────────────────────────────────────────────────────────
df = load_and_validate(uploaded)

income_df  = df[df["Type"].str.lower() == "income"]
expense_df = df[df["Type"].str.lower() == "expense"]

total_income  = income_df["Amount"].sum()
total_expense = abs(expense_df["Amount"].sum())   # amounts may be negative
balance       = total_income - total_expense

# ── Summary cards ─────────────────────────────────────────────────────────────
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

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(["📊 Dashboard", "🎯 Budget Insights", "💳 Recurring Bills & EMIs", "🛡️ Emergency Fund"])

with tab1:
    # ── AI Assistant Card ─────────────────────────────────────────────────────
    st.markdown('<div class="ai-card">', unsafe_allow_html=True)
    st.markdown('<div class="ai-title">🤖 AI Financial Assistant</div>', unsafe_allow_html=True)
    st.markdown('<div class="ai-subtitle">Ask me anything about your finances</div>', unsafe_allow_html=True)

    # Session state init
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = [{"role": "assistant", "text": WELCOME_MESSAGE}]

    # Chat history display
    for msg in st.session_state.chat_history:
        if msg["role"] == "user":
            st.markdown(f'<div class="chat-user">🧑 {msg["text"]}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="chat-bot">🤖 {msg["text"]}</div>', unsafe_allow_html=True)

    # Suggested questions
    st.markdown("**💬 Suggested Questions:**")
    sq_cols = st.columns(len(SUGGESTED_QUESTIONS))
    for i, sq in enumerate(SUGGESTED_QUESTIONS):
        if sq_cols[i].button(sq, key=f"sq_{i}", use_container_width=True):
            st.session_state._pending_question = sq

    # Chat input row
    col_input, col_send, col_mic = st.columns([6, 1, 1])
    with col_input:
        user_input = st.text_input(
            "Ask a question", label_visibility="collapsed",
            placeholder="Type your question here…", key="chat_input"
        )
    with col_send:
        send_clicked = st.button("Send 📨", use_container_width=True)
    with col_mic:
        mic_file = st.file_uploader("🎙️", type=["wav", "flac"], label_visibility="collapsed", key="mic_upload")

    # Handle mic input
    if mic_file is not None and stt_available():
        with st.spinner("🎙️ Transcribing audio…"):
            transcribed = speech_to_text_from_bytes(mic_file.read())
        if transcribed and not transcribed.startswith("Could not") and not transcribed.startswith("Error"):
            st.session_state._pending_question = transcribed
        else:
            st.warning(f"STT: {transcribed}")

    # Resolve question from input or suggested button
    question_to_ask = None
    if send_clicked and user_input.strip():
        question_to_ask = user_input.strip()
    elif "_pending_question" in st.session_state:
        question_to_ask = st.session_state.pop("_pending_question")

    if question_to_ask:
        st.session_state.chat_history.append({"role": "user", "text": question_to_ask})
        with st.spinner("🤔 Thinking…"):
            answer = generate_response(question_to_ask, df if uploaded else None)
        st.session_state.chat_history.append({"role": "assistant", "text": answer})
        # TTS playback
        if tts_available():
            plain = answer.replace("**", "").replace("#", "").replace("\n", " ")
            audio_html = text_to_speech_html(plain[:400])
            if audio_html:
                st.markdown(audio_html, unsafe_allow_html=True)
        st.rerun()

    if st.button("🗑️ Clear Chat", key="clear_chat"):
        st.session_state.chat_history = [{"role": "assistant", "text": WELCOME_MESSAGE}]
        st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    # ── Charts ────────────────────────────────────────────────────────────────
    col_pie, col_bar = st.columns(2)

    with col_pie:
        st.subheader("🍕 Expenses by Category")
        cat_data = expense_df.groupby("Category")["Amount"].apply(lambda x: abs(x).sum()).reset_index()
        cat_data.columns = ["Category", "Amount"]
        fig_pie = px.pie(
            cat_data, values="Amount", names="Category",
            color_discrete_sequence=px.colors.qualitative.Pastel,
            hole=0.4,
        )
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
        fig_bar = px.bar(
            monthly, x="Month", y="Amount", color="Type", barmode="group",
            color_discrete_map={"Income": "#4ade80", "Expense": "#f87171"},
        )
        fig_bar.update_layout(legend_title_text="", margin=dict(t=10, b=10))
        st.plotly_chart(fig_bar, use_container_width=True)

    # ── Transactions table ─────────────────────────────────────────────────────
    st.subheader("🔍 All Transactions")
    search = st.text_input("Search by description or category", placeholder="e.g. Amazon, Food…")
    display_df = df.copy()
    if search:
        mask = (
            display_df["Description"].str.contains(search, case=False, na=False) |
            display_df["Category"].str.contains(search, case=False, na=False)
        )
        display_df = display_df[mask]
    display_df["Date"] = display_df["Date"].dt.strftime("%Y-%m-%d")
    st.dataframe(
        display_df[["Date", "Description", "Amount", "Type", "Category"]],
        use_container_width=True,
        hide_index=True,
    )
    st.caption(f"Showing {len(display_df)} of {len(df)} transactions")

with tab2:
    budget_insights.render(expense_df)

with tab3:
    bill_insights.render(df)

with tab4:
    emergency_fund_insights.render(df)
