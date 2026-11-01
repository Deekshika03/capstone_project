"""
financial_assistant.py — AI Financial Assistant response engine for FinGuard AI.
Generates data-driven answers from actual user financial data.
"""

from __future__ import annotations

import pandas as pd
from typing import Optional


SUGGESTED_QUESTIONS = [
    "How can I save more money?",
    "Where am I spending the most?",
    "What is my financial health score?",
    "How much emergency fund should I maintain?",
    "Which EMI payments are upcoming?",
]

WELCOME_MESSAGE = (
    "Hello! I'm your Financial Friend AI. "
    "How can I help you manage your money today? 😊"
)


def _compute_basics(df: pd.DataFrame) -> dict:
    """Extract core financial metrics from the transactions DataFrame."""
    income_df = df[df["Type"].str.lower() == "income"]
    expense_df = df[df["Type"].str.lower() == "expense"]

    total_income = income_df["Amount"].sum()
    total_expense = abs(expense_df["Amount"].sum())
    balance = total_income - total_expense
    savings_rate = (balance / total_income * 100) if total_income > 0 else 0.0

    top_category = None
    top_amount = 0.0
    if not expense_df.empty and "Category" in expense_df.columns:
        cat_totals = expense_df.groupby("Category")["Amount"].apply(lambda x: abs(x).sum())
        top_category = cat_totals.idxmax()
        top_amount = cat_totals.max()

    return {
        "total_income": total_income,
        "total_expense": total_expense,
        "balance": balance,
        "savings_rate": savings_rate,
        "top_category": top_category,
        "top_amount": top_amount,
    }


def _health_score(savings_rate: float, balance: float, total_income: float) -> int:
    """Simple health score out of 100 based on savings rate and balance."""
    score = 0
    score += min(40, int(savings_rate * 0.8))          # up to 40 pts for savings rate
    if total_income > 0:
        balance_ratio = balance / total_income
        score += min(40, int(balance_ratio * 40))       # up to 40 pts for balance ratio
    score += 20 if savings_rate >= 20 else int(savings_rate)  # bonus for 20%+ savings
    return max(0, min(100, score))


def generate_response(question: str, df: Optional[pd.DataFrame]) -> str:
    """
    Generate a data-driven answer to the user's financial question.

    Parameters
    ----------
    question : user's question string
    df       : transactions DataFrame (may be None if no data uploaded)

    Returns
    -------
    Answer string (markdown supported)
    """
    q = question.lower().strip()

    if df is None or df.empty:
        return (
            "📂 I don't have your financial data yet. "
            "Please upload your transactions CSV in the Dashboard to get personalised answers!"
        )

    basics = _compute_basics(df)
    income = basics["total_income"]
    expense = basics["total_expense"]
    balance = basics["balance"]
    savings_rate = basics["savings_rate"]
    top_cat = basics["top_category"]
    top_amt = basics["top_amount"]
    score = _health_score(savings_rate, balance, income)

    # ── Save more money ───────────────────────────────────────────────────────
    if any(kw in q for kw in ["save", "saving", "savings"]):
        tips = []
        if top_cat:
            tips.append(f"- Your highest spending is **{top_cat}** (₹{top_amt:,.0f}). Try reducing it by 10–15%.")
        if savings_rate < 20:
            tips.append(f"- Your current savings rate is **{savings_rate:.1f}%**. Aim for at least **20%**.")
            tips.append(f"- That means saving ₹{income * 0.20:,.0f}/month from your income of ₹{income:,.0f}.")
        else:
            tips.append(f"- Great job! Your savings rate is **{savings_rate:.1f}%** — above the 20% benchmark. 🎉")
        tips.append("- Set up automatic transfers to a savings account on salary day.")
        tips.append("- Review subscriptions and cancel unused ones.")
        return "💡 **Here's how you can save more:**\n\n" + "\n".join(tips)

    # ── Spending most ─────────────────────────────────────────────────────────
    if any(kw in q for kw in ["spending", "spend", "most", "category", "categories", "where"]):
        if not top_cat:
            return "I couldn't find categorised expense data. Make sure your CSV has a Description column."
        expense_df = df[df["Type"].str.lower() == "expense"]
        cat_totals = expense_df.groupby("Category")["Amount"].apply(lambda x: abs(x).sum()).sort_values(ascending=False)
        lines = [f"- **{cat}**: ₹{amt:,.0f}" for cat, amt in cat_totals.items()]
        return (
            f"📊 **Your spending breakdown:**\n\n"
            + "\n".join(lines)
            + f"\n\n🔴 Highest category: **{top_cat}** at ₹{top_amt:,.0f}"
        )

    # ── Health score ──────────────────────────────────────────────────────────
    if any(kw in q for kw in ["health", "score", "risk", "financial health"]):
        if score >= 75:
            verdict = "🟢 Excellent! Your finances are in great shape."
        elif score >= 50:
            verdict = "🟡 Fair. There's room for improvement."
        else:
            verdict = "🔴 Needs attention. Focus on reducing expenses and building savings."
        return (
            f"🏆 **Your Financial Health Score: {score}/100**\n\n"
            f"{verdict}\n\n"
            f"- Income: ₹{income:,.0f}\n"
            f"- Expenses: ₹{expense:,.0f}\n"
            f"- Balance: ₹{balance:,.0f}\n"
            f"- Savings Rate: {savings_rate:.1f}%"
        )

    # ── Emergency fund ────────────────────────────────────────────────────────
    if any(kw in q for kw in ["emergency", "fund", "corpus", "maintain"]):
        monthly_expense = expense / max(df["Month"].nunique(), 1) if "Month" in df.columns else expense
        target_3m = monthly_expense * 3
        target_6m = monthly_expense * 6
        return (
            f"🛡️ **Emergency Fund Recommendation:**\n\n"
            f"Based on your monthly expenses of ₹{monthly_expense:,.0f}:\n\n"
            f"- **3-Month Target**: ₹{target_3m:,.0f} *(minimum)*\n"
            f"- **6-Month Target**: ₹{target_6m:,.0f} *(recommended)*\n"
            f"- **Senior Citizen (60+)**: ₹{monthly_expense * 8:,.0f} *(8 months with medical buffer)*\n\n"
            f"💡 Go to the **Emergency Fund** tab for a detailed milestone plan!"
        )

    # ── EMI / bills ───────────────────────────────────────────────────────────
    if any(kw in q for kw in ["emi", "bill", "payment", "upcoming", "due", "loan"]):
        return (
            "💳 **Upcoming EMI & Bill Payments:**\n\n"
            "Head over to the **Recurring Bills & EMIs** tab for a full breakdown of:\n"
            "- Detected recurring bills and EMIs\n"
            "- 30-day projected cash outflow\n"
            "- Priority alerts sorted by urgency\n\n"
            f"Your total expenses so far: ₹{expense:,.0f}"
        )

    # ── Income ────────────────────────────────────────────────────────────────
    if any(kw in q for kw in ["income", "earn", "salary"]):
        return (
            f"💰 **Your Income Summary:**\n\n"
            f"- Total Income: ₹{income:,.0f}\n"
            f"- Total Expenses: ₹{expense:,.0f}\n"
            f"- Net Balance: ₹{balance:,.0f}\n"
            f"- Savings Rate: {savings_rate:.1f}%"
        )

    # ── Balance ───────────────────────────────────────────────────────────────
    if any(kw in q for kw in ["balance", "left", "remaining", "net"]):
        return (
            f"💼 **Your Current Balance: ₹{balance:,.0f}**\n\n"
            f"- Income: ₹{income:,.0f}\n"
            f"- Expenses: ₹{expense:,.0f}"
        )

    # ── Budget ────────────────────────────────────────────────────────────────
    if any(kw in q for kw in ["budget", "overspend", "over budget"]):
        return (
            "🎯 **Budget Insights:**\n\n"
            "Go to the **Budget Insights** tab to:\n"
            "- Set category-wise budgets\n"
            "- See over-budget alerts\n"
            "- Get personalised saving suggestions\n\n"
            f"Your current expense total is ₹{expense:,.0f}."
        )

    # ── Help / fallback ───────────────────────────────────────────────────────
    return (
        "🤔 I'm not sure about that. Here are some things I can help with:\n\n"
        "- 💡 How can I save more money?\n"
        "- 📊 Where am I spending the most?\n"
        "- 🏆 What is my financial health score?\n"
        "- 🛡️ How much emergency fund should I maintain?\n"
        "- 💳 Which EMI payments are upcoming?"
    )
