import streamlit as st
import pandas as pd
import plotly.express as px
from modules import budget_insights, bill_insights, emergency_fund_insights
from src.assistant.financial_assistant import generate_response, SUGGESTED_QUESTIONS, WELCOME_MESSAGE
from src.assistant.voice import text_to_speech_html, speech_to_text_from_bytes, tts_available, stt_available

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Financial Friend AI",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Base ── */
[data-testid="stAppViewContainer"] {
    background: #f0f4ff;
    font-family: 'Segoe UI', sans-serif;
}
[data-testid="stHeader"] { background: transparent; }
[data-testid="stSidebar"] { background: #1e1b4b; }

/* ── Top header bar ── */
.top-header {
    background: linear-gradient(135deg, #1e1b4b 0%, #312e81 50%, #4c1d95 100%);
    border-radius: 16px;
    padding: 24px 32px;
    margin-bottom: 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.top-header-title { color: #fff; font-size: 26px; font-weight: 700; margin: 0; }
.top-header-sub   { color: #c4b5fd; font-size: 14px; margin-top: 4px; }
.top-header-badge {
    background: rgba(255,255,255,0.15);
    border-radius: 50px;
    padding: 6px 16px;
    color: #e0e7ff;
    font-size: 13px;
    font-weight: 600;
}

/* ── Metric cards ── */
.metric-card {
    background: #fff;
    border-radius: 14px;
    padding: 20px 24px;
    box-shadow: 0 2px 12px rgba(99,102,241,0.10);
    border-left: 4px solid #6366f1;
    margin-bottom: 8px;
}
.metric-card.income  { border-left-color: #10b981; }
.metric-card.expense { border-left-color: #ef4444; }
.metric-card.balance { border-left-color: #6366f1; }
.metric-card.score   { border-left-color: #f59e0b; }
.metric-label { color: #6b7280; font-size: 13px; font-weight: 500; margin-bottom: 6px; }
.metric-value { font-size: 26px; font-weight: 700; color: #111827; }
.metric-value.green  { color: #10b981; }
.metric-value.red    { color: #ef4444; }
.metric-value.blue   { color: #6366f1; }
.metric-value.amber  { color: #f59e0b; }

/* ── AI Assistant card ── */
.ai-assistant-card {
    background: linear-gradient(135deg, #1e1b4b 0%, #312e81 60%, #4c1d95 100%);
    border-radius: 20px;
    padding: 28px 32px;
    margin-bottom: 24px;
    box-shadow: 0 8px 32px rgba(99,102,241,0.25);
}
.ai-header {
    display: flex;
    align-items: center;
    gap: 14px;
    margin-bottom: 6px;
}
.ai-avatar {
    width: 52px; height: 52px;
    background: linear-gradient(135deg, #7c3aed, #4f46e5);
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 26px;
    box-shadow: 0 4px 12px rgba(124,58,237,0.4);
    flex-shrink: 0;
}
.ai-name  { color: #fff; font-size: 20px; font-weight: 700; }
.ai-tagline { color: #c4b5fd; font-size: 13px; margin-top: 2px; }
.ai-status {
    display: inline-block;
    width: 8px; height: 8px;
    background: #10b981;
    border-radius: 50%;
    margin-right: 6px;
    animation: pulse 2s infinite;
}
@keyframes pulse {
    0%,100% { opacity:1; } 50% { opacity:0.4; }
}

/* ── Chat bubbles ── */
.chat-container {
    max-height: 340px;
    overflow-y: auto;
    padding: 4px 0 12px 0;
    margin-bottom: 12px;
}
.chat-bubble-user {
    background: rgba(255,255,255,0.15);
    border-radius: 14px 14px 4px 14px;
    padding: 10px 16px;
    margin: 8px 0 8px 40px;
    color: #e0e7ff;
    font-size: 14px;
    line-height: 1.5;
}
.chat-bubble-bot {
    background: rgba(255,255,255,0.08);
    border-radius: 14px 14px 14px 4px;
    padding: 10px 16px;
    margin: 8px 40px 8px 0;
    color: #e0e7ff;
    font-size: 14px;
    line-height: 1.5;
    border-left: 3px solid #7c3aed;
}
.chat-sender-user { color: #a5b4fc; font-size: 11px; font-weight: 600; margin-bottom: 3px; text-align: right; }
.chat-sender-bot  { color: #c4b5fd; font-size: 11px; font-weight: 600; margin-bottom: 3px; }

/* ── Suggested question pills ── */
.sq-pill {
    display: inline-block;
    background: rgba(255,255,255,0.12);
    border: 1px solid rgba(255,255,255,0.2);
    border-radius: 50px;
    padding: 6px 14px;
    color: #e0e7ff;
    font-size: 12px;
    cursor: pointer;
    margin: 3px;
    transition: background 0.2s;
}
.sq-pill:hover { background: rgba(255,255,255,0.22); }

/* ── Section cards ── */
.section-card {
    background: #fff;
    border-radius: 16px;
    padding: 24px;
    box-shadow: 0 2px 12px rgba(99,102,241,0.08);
    margin-bottom: 20px;
}
.section-title {
    font-size: 16px;
    font-weight: 700;
    color: #1e1b4b;
    margin-bottom: 16px;
    display: flex;
    align-items: center;
    gap: 8px;
}

/* ── Upload zone ── */
.upload-zone {
    background: #fff;
    border: 2px dashed #c7d2fe;
    border-radius: 16px;
    padding: 32px;
    text-align: center;
    margin-bottom: 20px;
}
.upload-title { color: #1e1b4b; font-size: 18px; font-weight: 600; margin-bottom: 8px; }
.upload-sub   { color: #6b7280; font-size: 14px; }

/* ── Streamlit overrides ── */
div[data-testid="stTabs"] button {
    font-size: 14px !important;
    font-weight: 600 !important;
    color: #4b5563 !important;
    padding: 10px 20px !important;
}
div[data-testid="stTabs"] button[aria-selected="true"] {
    color: #4f46e5 !important;
    border-bottom: 3px solid #4f46e5 !important;
}
div[data-testid="stTabs"] { background: #fff; border-radius: 12px; padding: 4px 8px 0; box-shadow: 0 2px 8px rgba(99,102,241,0.08); margin-bottom: 16px; }
.stTextInput > div > div > input {
    border-radius: 10px !important;
    border: 1.5px solid #c7d2fe !important;
    font-size: 14px !important;
    padding: 10px 14px !important;
}
.stButton > button {
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 14px !important;
    transition: all 0.2s !important;
}
.stButton > button:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(99,102,241,0.2) !important; }
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

def categorize(desc: str) -> str:
    d = desc.lower()
    for cat, kws in CATEGORIES.items():
        if any(kw in d for kw in kws):
            return cat
    return "Other"

def load_and_validate(file) -> pd.DataFrame:
    df = pd.read_csv(file)
    required = {"Date", "Description", "Amount", "Type"}
    missing = required - set(df.columns)
    if missing:
        st.error(f"❌ Missing columns: {', '.join(missing)}.")
        st.stop()
    df.dropna(subset=["Date", "Amount", "Type"], inplace=True)
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
    df.dropna(subset=["Amount"], inplace=True)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df.dropna(subset=["Date"], inplace=True)
    df["Description"] = df["Description"].fillna("Unknown")
    df["Category"] = df["Description"].apply(categorize)
    df["Month"]    = df["Date"].dt.strftime("%b %Y")
    return df

def health_score(df: pd.DataFrame) -> int:
    inc = df[df["Type"].str.lower() == "income"]["Amount"].sum()
    exp = abs(df[df["Type"].str.lower() == "expense"]["Amount"].sum())
    bal = inc - exp
    sr  = (bal / inc * 100) if inc > 0 else 0
    s   = min(40, int(sr * 0.8))
    s  += min(40, int((bal / inc * 40) if inc > 0 else 0))
    s  += 20 if sr >= 20 else int(min(sr, 20))
    return max(0, min(100, s))

# ── Session state init ────────────────────────────────────────────────────────
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [{"role": "bot", "text": WELCOME_MESSAGE}]
if "tts_muted" not in st.session_state:
    st.session_state.tts_muted = False

# ── Top header ────────────────────────────────────────────────────────────────
st.markdown("""
<div class="top-header">
  <div>
    <div class="top-header-title">💰 Financial Friend AI</div>
    <div class="top-header-sub">Welcome Back! Your AI Financial Friend is here.</div>
  </div>
  <div class="top-header-badge">🤖 AI Powered</div>
</div>
""", unsafe_allow_html=True)

# ── File upload ───────────────────────────────────────────────────────────────
uploaded = st.file_uploader(
    "📂 Upload your bank transactions CSV (Date, Description, Amount, Type)",
    type="csv",
    help="Required columns: Date, Description, Amount, Type",
)

# ── Load data ─────────────────────────────────────────────────────────────────
df = None
income_df = expense_df = pd.DataFrame()
total_income = total_expense = balance = 0.0
score = 0

if uploaded:
    df = load_and_validate(uploaded)
    income_df    = df[df["Type"].str.lower() == "income"]
    expense_df   = df[df["Type"].str.lower() == "expense"]
    total_income  = income_df["Amount"].sum()
    total_expense = abs(expense_df["Amount"].sum())
    balance       = total_income - total_expense
    score         = health_score(df)

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "🏠 Dashboard",
    "🎯 Budget Insights",
    "💳 Recurring Bills & EMIs",
    "🛡️ Emergency Fund",
])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════
with tab1:

    # ── AI Assistant Card ─────────────────────────────────────────────────────
    st.markdown('<div class="ai-assistant-card">', unsafe_allow_html=True)

    # Header row
    st.markdown("""
    <div class="ai-header">
      <div class="ai-avatar">🤖</div>
      <div>
        <div class="ai-name"><span class="ai-status"></span>Financial Friend AI</div>
        <div class="ai-tagline">Your personal AI-powered financial advisor</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Chat history
    st.markdown('<div class="chat-container">', unsafe_allow_html=True)
    for msg in st.session_state.chat_history:
        if msg["role"] == "user":
            st.markdown(
                f'<div class="chat-sender-user">You</div>'
                f'<div class="chat-bubble-user">{msg["text"]}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div class="chat-sender-bot">🤖 Financial Friend AI</div>'
                f'<div class="chat-bubble-bot">{msg["text"]}</div>',
                unsafe_allow_html=True,
            )
    st.markdown('</div>', unsafe_allow_html=True)

    # Suggested questions
    st.markdown("**💬 Quick Questions:**")
    sq_cols = st.columns(len(SUGGESTED_QUESTIONS))
    for i, sq in enumerate(SUGGESTED_QUESTIONS):
        if sq_cols[i].button(sq, key=f"sq_{i}", use_container_width=True):
            st.session_state._pending_q = sq

    # Input row
    col_in, col_send, col_mic, col_mute = st.columns([5, 1, 1, 1])
    with col_in:
        user_input = st.text_input(
            "chat", label_visibility="collapsed",
            placeholder="Ask me anything about your finances…",
            key="chat_input",
        )
    with col_send:
        send = st.button("Send ➤", use_container_width=True, type="primary")
    with col_mic:
        mic_file = st.file_uploader(
            "mic", type=["wav", "flac"],
            label_visibility="collapsed", key="mic_upload",
        )
    with col_mute:
        mute_label = "🔇 Mute" if not st.session_state.tts_muted else "🔊 Unmute"
        if st.button(mute_label, use_container_width=True):
            st.session_state.tts_muted = not st.session_state.tts_muted
            st.rerun()

    # Mic STT
    if mic_file is not None and stt_available():
        with st.spinner("🎙️ Transcribing…"):
            transcribed = speech_to_text_from_bytes(mic_file.read())
        if transcribed and not transcribed.startswith(("Could not", "Error", "Speech")):
            st.session_state._pending_q = transcribed
        else:
            st.warning(f"🎙️ {transcribed}")

    # Resolve question
    question = None
    if send and user_input.strip():
        question = user_input.strip()
    elif "_pending_q" in st.session_state:
        question = st.session_state.pop("_pending_q")

    if question:
        st.session_state.chat_history.append({"role": "user", "text": question})
        with st.spinner("🤔 Thinking…"):
            answer = generate_response(question, df)
        st.session_state.chat_history.append({"role": "bot", "text": answer})
        # TTS
        if tts_available() and not st.session_state.tts_muted:
            plain = answer.replace("**", "").replace("#", "").replace("\n", " ")
            audio_html = text_to_speech_html(plain[:400])
            if audio_html:
                st.markdown(audio_html, unsafe_allow_html=True)
        st.rerun()

    # Clear chat
    if st.button("🗑️ Clear Chat", key="clear_chat"):
        st.session_state.chat_history = [{"role": "bot", "text": WELCOME_MESSAGE}]
        st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)  # close ai-assistant-card

    # ── No data state ─────────────────────────────────────────────────────────
    if df is None:
        st.markdown("""
        <div class="upload-zone">
          <div class="upload-title">📊 Upload Your Transactions to Get Started</div>
          <div class="upload-sub">Upload a CSV file above to unlock your full financial dashboard,<br>
          charts, health score, and personalised AI insights.</div>
        </div>
        """, unsafe_allow_html=True)
        with open("sample_transactions.csv", "rb") as f:
            st.download_button(
                "⬇️ Download Sample CSV to Try",
                f, "sample_transactions.csv", "text/csv",
            )
        st.stop()

    # ── Summary metric cards ──────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    m1, m2, m3, m4 = st.columns(4)
    metrics = [
        (m1, "💰 Total Income",   f"₹{total_income:,.0f}",  "income",  "green"),
        (m2, "💸 Total Expenses", f"₹{total_expense:,.0f}", "expense", "red"),
        (m3, "💼 Net Balance",    f"₹{balance:,.0f}",       "balance", "blue"),
        (m4, "🏆 Health Score",   f"{score}/100",           "score",   "amber"),
    ]
    for col, label, value, card_cls, val_cls in metrics:
        col.markdown(f"""
        <div class="metric-card {card_cls}">
            <div class="metric-label">{label}</div>
            <div class="metric-value {val_cls}">{value}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Charts ────────────────────────────────────────────────────────────────
    col_pie, col_bar = st.columns(2)

    with col_pie:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">🍩 Expenses by Category</div>', unsafe_allow_html=True)
        cat_data = expense_df.groupby("Category")["Amount"].apply(lambda x: abs(x).sum()).reset_index()
        cat_data.columns = ["Category", "Amount"]
        fig_pie = px.pie(
            cat_data, values="Amount", names="Category",
            color_discrete_sequence=["#6366f1","#8b5cf6","#a78bfa","#c4b5fd","#ddd6fe","#ede9fe"],
            hole=0.45,
        )
        fig_pie.update_traces(textposition="inside", textinfo="percent+label")
        fig_pie.update_layout(
            showlegend=True, margin=dict(t=10, b=10),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#374151"),
            legend=dict(orientation="h", yanchor="bottom", y=-0.3),
        )
        st.plotly_chart(fig_pie, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col_bar:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">📊 Monthly Income vs Expenses</div>', unsafe_allow_html=True)
        mi = income_df.groupby("Month")["Amount"].sum().reset_index()
        me = expense_df.groupby("Month")["Amount"].apply(lambda x: abs(x).sum()).reset_index()
        mi["Type"] = "Income"
        me["Type"] = "Expense"
        monthly = pd.concat([mi, me])
        month_order = df.sort_values("Date")["Month"].unique().tolist()
        monthly["Month"] = pd.Categorical(monthly["Month"], categories=month_order, ordered=True)
        monthly.sort_values("Month", inplace=True)
        fig_bar = px.bar(
            monthly, x="Month", y="Amount", color="Type", barmode="group",
            color_discrete_map={"Income": "#10b981", "Expense": "#ef4444"},
        )
        fig_bar.update_layout(
            legend_title_text="", margin=dict(t=10, b=10),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#374151"),
        )
        st.plotly_chart(fig_bar, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # ── Transactions table ────────────────────────────────────────────────────
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">🔍 All Transactions</div>', unsafe_allow_html=True)
    search = st.text_input("Search", placeholder="Search by description or category…", label_visibility="collapsed")
    disp = df.copy()
    if search:
        mask = (
            disp["Description"].str.contains(search, case=False, na=False) |
            disp["Category"].str.contains(search, case=False, na=False)
        )
        disp = disp[mask]
    disp["Date"] = disp["Date"].dt.strftime("%Y-%m-%d")
    st.dataframe(
        disp[["Date", "Description", "Amount", "Type", "Category"]],
        use_container_width=True, hide_index=True,
    )
    st.caption(f"Showing {len(disp)} of {len(df)} transactions")
    st.markdown('</div>', unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — BUDGET INSIGHTS
# ═══════════════════════════════════════════════════════════════════════════════
with tab2:
    if df is None:
        st.info("📂 Please upload a CSV in the Dashboard tab first.")
    else:
        budget_insights.render(expense_df)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — RECURRING BILLS & EMIs
# ═══════════════════════════════════════════════════════════════════════════════
with tab3:
    if df is None:
        st.info("📂 Please upload a CSV in the Dashboard tab first.")
    else:
        bill_insights.render(df)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4 — EMERGENCY FUND
# ═══════════════════════════════════════════════════════════════════════════════
with tab4:
    if df is None:
        st.info("📂 Please upload a CSV in the Dashboard tab first.")
    else:
        emergency_fund_insights.render(df)
