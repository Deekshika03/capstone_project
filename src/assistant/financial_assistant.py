"""
financial_assistant.py — AI Financial Assistant response engine for FinGuard AI.
Generates data-driven answers from actual user financial data across all modules.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

import pandas as pd

from src.planning.bill_tracker import BillTracker
from src.planning.emergency_fund import build_expense_profile, compute_emergency_corpus, analyse_fund_gap

SUGGESTED_QUESTIONS = [
    "How can I reduce my monthly expenses?",
    "Where am I spending the most?",
    "What is my financial health score?",
    "How much emergency fund do I need?",
    "Which EMI payments are upcoming?",
]

WELCOME_MESSAGE = (
    "Hello! 👋 I'm your **Financial Friend AI**. "
    "I can analyse your expenses, check your financial health, track EMIs, "
    "and help you build your emergency fund. How can I help you today? 😊"
)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _basics(df: pd.DataFrame) -> dict:
    inc = df[df["Type"].str.lower() == "income"]
    exp = df[df["Type"].str.lower() == "expense"]
    total_income  = inc["Amount"].sum()
    total_expense = abs(exp["Amount"].sum())
    balance       = total_income - total_expense
    savings_rate  = (balance / total_income * 100) if total_income > 0 else 0.0
    months        = df["Month"].nunique() if "Month" in df.columns else 1
    monthly_exp   = total_expense / max(months, 1)

    top_cat, top_amt = None, 0.0
    if not exp.empty and "Category" in exp.columns:
        cat_totals = exp.groupby("Category")["Amount"].apply(lambda x: abs(x).sum())
        top_cat    = cat_totals.idxmax()
        top_amt    = cat_totals.max()

    return {
        "income": total_income, "expense": total_expense,
        "balance": balance, "savings_rate": savings_rate,
        "monthly_expense": monthly_exp, "months": months,
        "top_cat": top_cat, "top_amt": top_amt,
        "income_df": inc, "expense_df": exp,
    }


def _health_score(savings_rate: float, balance: float, income: float) -> int:
    score  = min(40, int(savings_rate * 0.8))
    score += min(40, int((balance / income * 40) if income > 0 else 0))
    score += 20 if savings_rate >= 20 else int(min(savings_rate, 20))
    return max(0, min(100, score))


def _no_data_msg() -> str:
    return (
        "📂 I don't have your financial data yet. "
        "Please upload your transactions CSV in the Dashboard to get personalised answers!"
    )


# ── Public API ────────────────────────────────────────────────────────────────

def generate_response(
    question: str,
    df: Optional[pd.DataFrame],
    tts_muted: bool = False,
) -> str:
    """
    Generate a data-driven answer to the user's financial question.
    Uses bill_tracker and emergency_fund modules for richer answers.
    """
    if df is None or df.empty:
        return _no_data_msg()

    q = question.lower().strip()
    b = _basics(df)
    income, expense, balance = b["income"], b["expense"], b["balance"]
    savings_rate, monthly_exp = b["savings_rate"], b["monthly_expense"]
    top_cat, top_amt = b["top_cat"], b["top_amt"]
    score = _health_score(savings_rate, balance, income)

    # ── Reduce / save money ───────────────────────────────────────────────────
    if any(kw in q for kw in ["reduce", "save", "saving", "cut", "less", "lower"]):
        exp_df = b["expense_df"]
        tips = []
        if top_cat:
            tips.append(f"- 🔴 Highest spend: **{top_cat}** — ₹{top_amt:,.0f}. Try cutting it by 10–15% (saves ₹{top_amt*0.12:,.0f}/month).")
        if savings_rate < 20:
            target_save = income * 0.20
            tips.append(f"- 📉 Savings rate is **{savings_rate:.1f}%** — below the 20% benchmark. Aim to save ₹{target_save:,.0f}/month.")
        else:
            tips.append(f"- ✅ Savings rate is **{savings_rate:.1f}%** — above 20% benchmark. Great discipline!")
        if "Category" in exp_df.columns:
            cat_totals = exp_df.groupby("Category")["Amount"].apply(lambda x: abs(x).sum()).sort_values(ascending=False)
            for cat, amt in list(cat_totals.items())[:3]:
                tips.append(f"- **{cat}**: ₹{amt:,.0f} total → ₹{amt/b['months']:,.0f}/month avg")
        tips.append("- 💡 Set up auto-transfer to savings on salary day.")
        tips.append("- 💡 Review and cancel unused subscriptions.")
        return "💡 **Ways to Reduce Your Monthly Expenses:**\n\n" + "\n".join(tips)

    # ── Spending breakdown ────────────────────────────────────────────────────
    if any(kw in q for kw in ["spending", "spend", "most", "category", "where", "breakdown"]):
        exp_df = b["expense_df"]
        if not top_cat:
            return "I couldn't find categorised expense data. Make sure your CSV has a Description column."
        cat_totals = exp_df.groupby("Category")["Amount"].apply(lambda x: abs(x).sum()).sort_values(ascending=False)
        lines = [f"- **{cat}**: ₹{amt:,.0f} (₹{amt/b['months']:,.0f}/month)" for cat, amt in cat_totals.items()]
        return (
            f"📊 **Your Spending Breakdown ({b['months']} month(s)):**\n\n"
            + "\n".join(lines)
            + f"\n\n🔴 Top category: **{top_cat}** — ₹{top_amt:,.0f} total"
        )

    # ── Health score ──────────────────────────────────────────────────────────
    if any(kw in q for kw in ["health", "score", "risk", "financial health", "rating"]):
        verdict = (
            "🟢 **Excellent!** Your finances are in great shape."
            if score >= 75 else
            "🟡 **Fair.** There's room for improvement — focus on savings."
            if score >= 50 else
            "🔴 **Needs Attention.** Reduce expenses and build your savings buffer."
        )
        breakdown = []
        breakdown.append(f"- Savings Rate: {savings_rate:.1f}% {'✅' if savings_rate >= 20 else '⚠️'}")
        breakdown.append(f"- Income: ₹{income:,.0f}")
        breakdown.append(f"- Expenses: ₹{expense:,.0f}")
        breakdown.append(f"- Net Balance: ₹{balance:,.0f}")
        if top_cat:
            breakdown.append(f"- Biggest Expense: {top_cat} (₹{top_amt:,.0f})")
        return (
            f"🏆 **Financial Health Score: {score}/100**\n\n"
            f"{verdict}\n\n"
            + "\n".join(breakdown)
            + "\n\n💡 Go to the **Budget Insights** tab for category-wise budget tracking."
        )

    # ── Emergency fund ────────────────────────────────────────────────────────
    if any(kw in q for kw in ["emergency", "fund", "corpus", "maintain", "safety", "need"]):
        try:
            profile = build_expense_profile(df)
            corpus  = compute_emergency_corpus(profile)
            return (
                f"🛡️ **Emergency Fund Recommendation:**\n\n"
                f"Based on your monthly essential expenses of ₹{profile.monthly_essential:,.0f}:\n\n"
                f"- **3-Month Target** *(minimum)*: ₹{corpus.target_3m:,.0f}\n"
                f"- **6-Month Target** *(recommended)*: ₹{corpus.target_6m:,.0f}\n"
                f"- **Senior Citizen (60+)**: ₹{corpus.target_senior:,.0f} *(8 months with medical buffer)*\n\n"
                f"💡 Go to the **Emergency Fund** tab for a full milestone plan and action steps!"
            )
        except Exception:
            target_3m = monthly_exp * 3
            target_6m = monthly_exp * 6
            return (
                f"🛡️ **Emergency Fund Recommendation:**\n\n"
                f"Based on monthly expenses of ₹{monthly_exp:,.0f}:\n\n"
                f"- **3-Month Target**: ₹{target_3m:,.0f}\n"
                f"- **6-Month Target**: ₹{target_6m:,.0f}\n\n"
                f"💡 Go to the **Emergency Fund** tab for a detailed plan!"
            )

    # ── EMI / bills ───────────────────────────────────────────────────────────
    if any(kw in q for kw in ["emi", "bill", "payment", "upcoming", "due", "loan", "recurring"]):
        try:
            tracker = BillTracker(df, min_occurrences=2)
            bills   = tracker.recurring_bills
            emis    = tracker.get_emis()
            proj    = tracker.cash_outflow_projection
            alerts  = tracker.get_alerts_by_urgency()

            if not bills:
                return (
                    "💳 **Recurring Bills & EMIs:**\n\n"
                    "No recurring patterns detected in your data yet. "
                    "Upload more months of transactions for better detection.\n\n"
                    f"Total expenses so far: ₹{expense:,.0f}"
                )

            lines = [f"- **{b.name}**: ₹{b.expected_amount:,.0f}/{b.frequency} (next: {b.next_due_date}){'  🏦 EMI' if b.is_emi else ''}" for b in bills[:5]]
            result = (
                f"💳 **Recurring Bills & EMIs Detected:**\n\n"
                + "\n".join(lines)
                + f"\n\n📊 **30-Day Projected Outflow**: ₹{proj.total_projected_outflow:,.0f}"
                + f"\n🏦 **EMI Outflow**: ₹{proj.total_emi_outflow:,.0f}"
            )
            if alerts:
                top_alert = alerts[0]
                result += f"\n\n🚨 **Top Alert**: {top_alert.title} — {top_alert.message[:120]}..."
            result += "\n\n💡 Go to the **Recurring Bills & EMIs** tab for full details and priority alerts."
            return result
        except Exception:
            return (
                "💳 **Upcoming EMI & Bill Payments:**\n\n"
                "Head to the **Recurring Bills & EMIs** tab for a full breakdown.\n\n"
                f"Total expenses so far: ₹{expense:,.0f}"
            )

    # ── Income ────────────────────────────────────────────────────────────────
    if any(kw in q for kw in ["income", "earn", "salary", "revenue"]):
        monthly_inc = income / max(b["months"], 1)
        return (
            f"💰 **Your Income Summary:**\n\n"
            f"- Total Income: ₹{income:,.0f}\n"
            f"- Monthly Average: ₹{monthly_inc:,.0f}\n"
            f"- Total Expenses: ₹{expense:,.0f}\n"
            f"- Net Balance: ₹{balance:,.0f}\n"
            f"- Savings Rate: {savings_rate:.1f}%"
        )

    # ── Balance ───────────────────────────────────────────────────────────────
    if any(kw in q for kw in ["balance", "left", "remaining", "net", "how much"]):
        return (
            f"💼 **Your Current Balance: ₹{balance:,.0f}**\n\n"
            f"- Income: ₹{income:,.0f}\n"
            f"- Expenses: ₹{expense:,.0f}\n"
            f"- Savings Rate: {savings_rate:.1f}%"
        )

    # ── Budget ────────────────────────────────────────────────────────────────
    if any(kw in q for kw in ["budget", "overspend", "over budget", "limit"]):
        return (
            f"🎯 **Budget Insights:**\n\n"
            f"Your current expense total is ₹{expense:,.0f}.\n\n"
            "Go to the **Budget Insights** tab to:\n"
            "- Set category-wise budgets\n"
            "- See over-budget alerts\n"
            "- Get personalised saving suggestions"
        )

    # ── Fallback ──────────────────────────────────────────────────────────────
    return (
        "🤔 I'm not sure about that. Here are things I can help with:\n\n"
        "- 💡 How can I reduce my monthly expenses?\n"
        "- 📊 Where am I spending the most?\n"
        "- 🏆 What is my financial health score?\n"
        "- 🛡️ How much emergency fund do I need?\n"
        "- 💳 Which EMI payments are upcoming?"
    )
