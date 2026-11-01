"""
financial_context.py — Centralized financial context provider for Financial Friend AI.
Collects data from all existing modules without duplicating calculations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from src.planning.bill_tracker import BillTracker
from src.planning.emergency_fund import build_expense_profile, compute_emergency_corpus, analyse_fund_gap


@dataclass
class FinancialContext:
    """Aggregated financial snapshot derived from user transaction data."""
    # Core metrics
    total_income: float = 0.0
    total_expense: float = 0.0
    balance: float = 0.0
    savings_rate: float = 0.0
    months_analysed: int = 1
    monthly_income: float = 0.0
    monthly_expense: float = 0.0

    # Health score (0–100)
    health_score: int = 0

    # Spending breakdown
    top_category: Optional[str] = None
    top_category_amount: float = 0.0
    category_breakdown: dict = field(default_factory=dict)   # {cat: total}

    # Emergency fund
    monthly_essential: float = 0.0
    target_3m: float = 0.0
    target_6m: float = 0.0
    target_senior: float = 0.0

    # Bills & EMIs
    recurring_bills: list = field(default_factory=list)
    emi_count: int = 0
    projected_outflow_30d: float = 0.0
    emi_outflow_30d: float = 0.0
    top_alert_title: str = ""
    top_alert_message: str = ""

    # AI Insights (generated strings)
    insights: list = field(default_factory=list)       # list[str]
    action_steps: list = field(default_factory=list)   # list[str]

    has_data: bool = False


def _compute_health_score(savings_rate: float, balance: float, income: float) -> int:
    s  = min(40, int(savings_rate * 0.8))
    s += min(40, int((balance / income * 40) if income > 0 else 0))
    s += 20 if savings_rate >= 20 else int(min(savings_rate, 20))
    return max(0, min(100, s))


def _generate_insights(ctx: FinancialContext) -> list[str]:
    """Generate 3–5 personalized insight strings from the context."""
    insights = []

    if ctx.savings_rate < 10:
        insights.append(f"⚠️ Your savings rate is only {ctx.savings_rate:.1f}%. Try to save at least 20% of income.")
    elif ctx.savings_rate < 20:
        insights.append(f"📈 Savings rate {ctx.savings_rate:.1f}% — close to the 20% target. Small cuts can get you there.")
    else:
        insights.append(f"✅ Great savings rate of {ctx.savings_rate:.1f}%! Keep it up.")

    if ctx.top_category:
        pct = (ctx.top_category_amount / ctx.total_expense * 100) if ctx.total_expense > 0 else 0
        insights.append(f"🔴 **{ctx.top_category}** is your biggest expense ({pct:.0f}% of total). Consider reducing it by 10–15%.")

    if ctx.target_6m > 0 and ctx.balance < ctx.target_3m:
        insights.append(f"🛡️ Your balance (₹{ctx.balance:,.0f}) is below the 3-month emergency target (₹{ctx.target_3m:,.0f}). Prioritise building your safety net.")

    if ctx.emi_outflow_30d > 0:
        emi_pct = (ctx.emi_outflow_30d / ctx.monthly_income * 100) if ctx.monthly_income > 0 else 0
        if emi_pct > 40:
            insights.append(f"💳 EMI payments consume {emi_pct:.0f}% of your monthly income. Consider refinancing to reduce the burden.")
        else:
            insights.append(f"💳 EMI outflow next 30 days: ₹{ctx.emi_outflow_30d:,.0f} ({emi_pct:.0f}% of income) — manageable.")

    if ctx.health_score < 50:
        insights.append("🏥 Your financial health score needs attention. Focus on reducing discretionary spending first.")

    return insights[:5]


def _generate_action_steps(ctx: FinancialContext) -> list[str]:
    """Generate quick action steps."""
    steps = []
    if ctx.savings_rate < 20:
        target = ctx.monthly_income * 0.20
        steps.append(f"Set up auto-transfer of ₹{target:,.0f}/month to savings on salary day.")
    if ctx.top_category:
        cut = ctx.top_category_amount * 0.12 / max(ctx.months_analysed, 1)
        steps.append(f"Cut {ctx.top_category} spending by 10% → saves ₹{cut:,.0f}/month.")
    if ctx.balance < ctx.target_3m and ctx.target_3m > 0:
        gap = ctx.target_3m - ctx.balance
        steps.append(f"Build emergency fund: need ₹{gap:,.0f} more to reach 3-month safety net.")
    steps.append("Review and cancel unused subscriptions (streaming, apps).")
    steps.append("Check Budget Insights tab to set category-wise spending limits.")
    return steps[:4]


def build_financial_context(df: Optional[pd.DataFrame]) -> FinancialContext:
    """
    Build a complete FinancialContext from the user's transactions DataFrame.
    Reuses existing module calculations — no duplication.

    Parameters
    ----------
    df : transactions DataFrame (may be None)

    Returns
    -------
    FinancialContext with has_data=False if df is None/empty.
    """
    ctx = FinancialContext()

    if df is None or df.empty:
        return ctx

    ctx.has_data = True

    # ── Core metrics ──────────────────────────────────────────────────────────
    inc_df = df[df["Type"].str.lower() == "income"]
    exp_df = df[df["Type"].str.lower() == "expense"]

    ctx.total_income  = inc_df["Amount"].sum()
    ctx.total_expense = abs(exp_df["Amount"].sum())
    ctx.balance       = ctx.total_income - ctx.total_expense
    ctx.savings_rate  = (ctx.balance / ctx.total_income * 100) if ctx.total_income > 0 else 0.0
    ctx.months_analysed = df["Month"].nunique() if "Month" in df.columns else 1
    ctx.monthly_income  = ctx.total_income  / max(ctx.months_analysed, 1)
    ctx.monthly_expense = ctx.total_expense / max(ctx.months_analysed, 1)
    ctx.health_score    = _compute_health_score(ctx.savings_rate, ctx.balance, ctx.total_income)

    # ── Spending breakdown ────────────────────────────────────────────────────
    if not exp_df.empty and "Category" in exp_df.columns:
        cat_totals = exp_df.groupby("Category")["Amount"].apply(lambda x: abs(x).sum())
        ctx.category_breakdown = cat_totals.to_dict()
        ctx.top_category        = cat_totals.idxmax()
        ctx.top_category_amount = cat_totals.max()

    # ── Emergency fund (reuse existing module) ────────────────────────────────
    try:
        profile = build_expense_profile(df)
        corpus  = compute_emergency_corpus(profile)
        ctx.monthly_essential = profile.monthly_essential
        ctx.target_3m         = corpus.target_3m
        ctx.target_6m         = corpus.target_6m
        ctx.target_senior     = corpus.target_senior
    except Exception:
        ctx.monthly_essential = ctx.monthly_expense * 0.6
        ctx.target_3m         = ctx.monthly_essential * 3
        ctx.target_6m         = ctx.monthly_essential * 6
        ctx.target_senior     = ctx.monthly_essential * 8

    # ── Bills & EMIs (reuse existing module) ─────────────────────────────────
    try:
        tracker = BillTracker(df, min_occurrences=2)
        ctx.recurring_bills      = tracker.recurring_bills
        ctx.emi_count            = len(tracker.get_emis())
        proj = tracker.cash_outflow_projection
        if proj:
            ctx.projected_outflow_30d = proj.total_projected_outflow
            ctx.emi_outflow_30d       = proj.total_emi_outflow
        alerts = tracker.get_alerts_by_urgency()
        if alerts:
            ctx.top_alert_title   = alerts[0].title
            ctx.top_alert_message = alerts[0].message
    except Exception:
        pass

    # ── AI Insights & Action Steps ────────────────────────────────────────────
    ctx.insights      = _generate_insights(ctx)
    ctx.action_steps  = _generate_action_steps(ctx)

    return ctx
