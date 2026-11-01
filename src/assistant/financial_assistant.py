"""
financial_assistant.py — AI response engine for Financial Friend AI.
Uses FinancialContext (centralized data) and prompts module.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from src.assistant.financial_context import FinancialContext, build_financial_context
from src.assistant.prompts import detect_intent, FALLBACK_RESPONSE, NO_DATA_RESPONSE

SUGGESTED_QUESTIONS = [
    "How can I reduce my expenses?",
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


# ── Intent handlers ───────────────────────────────────────────────────────────

def _handle_reduce_expenses(ctx: FinancialContext) -> str:
    tips = []
    if ctx.top_category:
        monthly_top = ctx.top_category_amount / max(ctx.months_analysed, 1)
        tips.append(f"- 🔴 Highest spend: **{ctx.top_category}** — ₹{monthly_top:,.0f}/month. Cut by 10–15% to save ₹{monthly_top*0.12:,.0f}/month.")
    if ctx.savings_rate < 20:
        tips.append(f"- 📉 Savings rate **{ctx.savings_rate:.1f}%** — below 20% benchmark. Target: ₹{ctx.monthly_income*0.20:,.0f}/month.")
    else:
        tips.append(f"- ✅ Savings rate **{ctx.savings_rate:.1f}%** — above 20% benchmark. Great discipline!")
    for cat, amt in sorted(ctx.category_breakdown.items(), key=lambda x: -x[1])[:3]:
        tips.append(f"- **{cat}**: ₹{amt/max(ctx.months_analysed,1):,.0f}/month avg")
    tips.append("- 💡 Set up auto-transfer to savings on salary day.")
    tips.append("- 💡 Review and cancel unused subscriptions.")
    return "💡 **Ways to Reduce Your Monthly Expenses:**\n\n" + "\n".join(tips)


def _handle_spending_breakdown(ctx: FinancialContext) -> str:
    if not ctx.top_category:
        return "I couldn't find categorised expense data. Make sure your CSV has a Description column."
    lines = [
        f"- **{cat}**: ₹{amt:,.0f} (₹{amt/max(ctx.months_analysed,1):,.0f}/month)"
        for cat, amt in sorted(ctx.category_breakdown.items(), key=lambda x: -x[1])
    ]
    return (
        f"📊 **Your Spending Breakdown ({ctx.months_analysed} month(s)):**\n\n"
        + "\n".join(lines)
        + f"\n\n🔴 Top category: **{ctx.top_category}** — ₹{ctx.top_category_amount:,.0f} total"
    )


def _handle_health_score(ctx: FinancialContext) -> str:
    if ctx.health_score >= 75:
        verdict = "🟢 **Excellent!** Your finances are in great shape."
    elif ctx.health_score >= 50:
        verdict = "🟡 **Fair.** There's room for improvement — focus on savings."
    else:
        verdict = "🔴 **Needs Attention.** Reduce expenses and build your savings buffer."
    lines = [
        f"- Savings Rate: {ctx.savings_rate:.1f}% {'✅' if ctx.savings_rate >= 20 else '⚠️'}",
        f"- Income: ₹{ctx.total_income:,.0f}",
        f"- Expenses: ₹{ctx.total_expense:,.0f}",
        f"- Net Balance: ₹{ctx.balance:,.0f}",
    ]
    if ctx.top_category:
        lines.append(f"- Biggest Expense: {ctx.top_category} (₹{ctx.top_category_amount:,.0f})")
    return (
        f"🏆 **Financial Health Score: {ctx.health_score}/100**\n\n"
        f"{verdict}\n\n"
        + "\n".join(lines)
        + "\n\n💡 Go to the **Budget Insights** tab for category-wise budget tracking."
    )


def _handle_emergency_fund(ctx: FinancialContext) -> str:
    return (
        f"🛡️ **Emergency Fund Recommendation:**\n\n"
        f"Based on your monthly essential expenses of ₹{ctx.monthly_essential:,.0f}:\n\n"
        f"- **3-Month Target** *(minimum)*: ₹{ctx.target_3m:,.0f}\n"
        f"- **6-Month Target** *(recommended)*: ₹{ctx.target_6m:,.0f}\n"
        f"- **Senior Citizen (60+)**: ₹{ctx.target_senior:,.0f} *(8 months with medical buffer)*\n\n"
        f"💡 Go to the **Emergency Fund** tab for a full milestone plan and action steps!"
    )


def _handle_emi_bills(ctx: FinancialContext) -> str:
    if not ctx.recurring_bills:
        return (
            "💳 **Recurring Bills & EMIs:**\n\n"
            "No recurring patterns detected yet. Upload more months of transactions.\n\n"
            f"Total expenses so far: ₹{ctx.total_expense:,.0f}"
        )
    lines = [
        f"- **{b.name}**: ₹{b.expected_amount:,.0f}/{b.frequency} (next: {b.next_due_date})"
        f"{'  🏦 EMI' if b.is_emi else ''}"
        for b in ctx.recurring_bills[:5]
    ]
    result = (
        f"💳 **Recurring Bills & EMIs Detected:**\n\n"
        + "\n".join(lines)
        + f"\n\n📊 **30-Day Projected Outflow**: ₹{ctx.projected_outflow_30d:,.0f}"
        + f"\n🏦 **EMI Outflow**: ₹{ctx.emi_outflow_30d:,.0f}"
    )
    if ctx.top_alert_title:
        result += f"\n\n🚨 **Top Alert**: {ctx.top_alert_title} — {ctx.top_alert_message[:100]}..."
    result += "\n\n💡 Go to the **Recurring Bills & EMIs** tab for full details."
    return result


def _handle_income(ctx: FinancialContext) -> str:
    return (
        f"💰 **Your Income Summary:**\n\n"
        f"- Total Income: ₹{ctx.total_income:,.0f}\n"
        f"- Monthly Average: ₹{ctx.monthly_income:,.0f}\n"
        f"- Total Expenses: ₹{ctx.total_expense:,.0f}\n"
        f"- Net Balance: ₹{ctx.balance:,.0f}\n"
        f"- Savings Rate: {ctx.savings_rate:.1f}%"
    )


def _handle_balance(ctx: FinancialContext) -> str:
    return (
        f"💼 **Your Current Balance: ₹{ctx.balance:,.0f}**\n\n"
        f"- Income: ₹{ctx.total_income:,.0f}\n"
        f"- Expenses: ₹{ctx.total_expense:,.0f}\n"
        f"- Savings Rate: {ctx.savings_rate:.1f}%"
    )


def _handle_budget(ctx: FinancialContext) -> str:
    return (
        f"🎯 **Budget Insights:**\n\n"
        f"Your current expense total is ₹{ctx.total_expense:,.0f}.\n\n"
        "Go to the **Budget Insights** tab to:\n"
        "- Set category-wise budgets\n"
        "- See over-budget alerts\n"
        "- Get personalised saving suggestions"
    )


_HANDLERS = {
    "reduce_expenses":    _handle_reduce_expenses,
    "spending_breakdown": _handle_spending_breakdown,
    "health_score":       _handle_health_score,
    "emergency_fund":     _handle_emergency_fund,
    "emi_bills":          _handle_emi_bills,
    "income":             _handle_income,
    "balance":            _handle_balance,
    "budget":             _handle_budget,
}


# ── Public API ────────────────────────────────────────────────────────────────

def generate_response(
    question: str,
    df: Optional[pd.DataFrame],
    ctx: Optional[FinancialContext] = None,
) -> str:
    """
    Generate a data-driven answer to the user's financial question.

    Parameters
    ----------
    question : user question string
    df       : transactions DataFrame (may be None)
    ctx      : pre-built FinancialContext (optional — built from df if not provided)
    """
    if df is None or (hasattr(df, "empty") and df.empty):
        return NO_DATA_RESPONSE

    if ctx is None:
        ctx = build_financial_context(df)

    if not ctx.has_data:
        return NO_DATA_RESPONSE

    intent = detect_intent(question)
    handler = _HANDLERS.get(intent)
    if handler:
        return handler(ctx)
    return FALLBACK_RESPONSE
