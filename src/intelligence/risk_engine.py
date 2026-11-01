"""
risk_engine.py — Chunk 5
Explainable Financial Risk Score (0 = safe, 100 = high risk).

Factors & max weights:
  EMI Burden Ratio        → up to 35 pts
  Spending Volatility     → up to 25 pts
  Buffer Liquidity        → up to 25 pts
  Savings Rate            → up to 15 pts
"""

from dataclasses import dataclass, field
from statistics import mean, stdev
from typing import Optional

from src.ingestion.transaction import Transaction


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class RiskResult:
    score: int                          # 0–100
    label: str                          # Safe / Moderate / High Risk / Critical
    factors: dict[str, float]           # raw computed values per factor
    factor_scores: dict[str, int]       # risk points contributed per factor
    explanations: list[str]             # human-readable bullet points
    recommendations: list[str]          # actionable advice


# ── Factor helpers ────────────────────────────────────────────────────────────

def _emi_burden_score(emi_total: float, monthly_income: float) -> tuple[int, float, str]:
    """
    EMI burden = EMI / income.
    0–30%  → 0 pts   (healthy)
    30–50% → 15 pts  (moderate)
    50–70% → 25 pts  (high)
    >70%   → 35 pts  (critical)
    """
    if monthly_income <= 0:
        return 35, 1.0, "Income data unavailable — assuming worst case."
    ratio = emi_total / monthly_income
    if ratio < 0.30:
        pts, msg = 0,  f"✅ EMI burden is {ratio*100:.1f}% of income — healthy."
    elif ratio < 0.50:
        pts, msg = 15, f"⚠️ +15 Risk: EMI consumes {ratio*100:.1f}% of monthly income."
    elif ratio < 0.70:
        pts, msg = 25, f"🔴 +25 Risk: EMI consumes {ratio*100:.1f}% of monthly income — high burden."
    else:
        pts, msg = 35, f"🚨 +35 Risk: EMI consumes {ratio*100:.1f}% of monthly income — critical."
    return pts, ratio, msg


def _volatility_score(monthly_expenses: list[float]) -> tuple[int, float, str]:
    """
    Coefficient of variation (CV) of monthly expenses.
    CV < 0.15  → 0 pts   (stable)
    CV < 0.30  → 10 pts  (moderate)
    CV < 0.50  → 18 pts  (erratic)
    CV >= 0.50 → 25 pts  (highly erratic)
    """
    if len(monthly_expenses) < 2:
        return 0, 0.0, "ℹ️ Not enough months to assess spending volatility."
    avg = mean(monthly_expenses)
    if avg == 0:
        return 0, 0.0, "✅ No expense data to assess volatility."
    cv = stdev(monthly_expenses) / avg
    if cv < 0.15:
        pts, msg = 0,  f"✅ Spending is stable (CV={cv:.2f})."
    elif cv < 0.30:
        pts, msg = 10, f"⚠️ +10 Risk: Moderate spending volatility detected (CV={cv:.2f})."
    elif cv < 0.50:
        pts, msg = 18, f"🔴 +18 Risk: Erratic spending pattern (CV={cv:.2f}) — review large irregular expenses."
    else:
        pts, msg = 25, f"🚨 +25 Risk: Highly erratic withdrawals (CV={cv:.2f}) — spending is unpredictable."
    return pts, cv, msg


def _liquidity_score(current_balance: float, avg_monthly_expense: float) -> tuple[int, float, str]:
    """
    Buffer = balance / avg_monthly_expense (days of cash).
    > 90 days  → 0 pts
    60–90 days → 8 pts
    30–60 days → 15 pts
    < 30 days  → 25 pts
    """
    if avg_monthly_expense <= 0:
        return 0, 999.0, "✅ No expenses recorded — liquidity risk is zero."
    daily_burn = avg_monthly_expense / 30
    days = current_balance / daily_burn if daily_burn > 0 else 999
    if days > 90:
        pts, msg = 0,  f"✅ Buffer liquidity is {days:.0f} days of cash — excellent."
    elif days > 60:
        pts, msg = 8,  f"⚠️ +8 Risk: {days:.0f} days of cash remaining — build emergency fund."
    elif days > 30:
        pts, msg = 15, f"🔴 +15 Risk: Only {days:.0f} days of cash buffer — vulnerable to shocks."
    else:
        pts, msg = 25, f"🚨 +25 Risk: Critical — only {days:.0f} days of cash remaining."
    return pts, days, msg


def _savings_score(monthly_income: float, avg_monthly_expense: float) -> tuple[int, float, str]:
    """
    Savings rate = (income - expense) / income.
    > 20%      → 0 pts
    10–20%     → 5 pts
    0–10%      → 10 pts
    Negative   → 15 pts
    """
    if monthly_income <= 0:
        return 15, -1.0, "🚨 +15 Risk: No income detected."
    rate = (monthly_income - avg_monthly_expense) / monthly_income
    if rate > 0.20:
        pts, msg = 0,  f"✅ Savings rate is {rate*100:.1f}% — great financial discipline."
    elif rate > 0.10:
        pts, msg = 5,  f"⚠️ +5 Risk: Savings rate is {rate*100:.1f}% — aim for 20%+."
    elif rate >= 0:
        pts, msg = 10, f"🔴 +10 Risk: Savings rate is only {rate*100:.1f}% — barely saving."
    else:
        pts, msg = 15, f"🚨 +15 Risk: Spending exceeds income by {abs(rate)*100:.1f}% — deficit spending."
    return pts, rate, msg


def _label(score: int) -> str:
    if score <= 25:  return "Safe"
    if score <= 50:  return "Moderate"
    if score <= 75:  return "High Risk"
    return "Critical"


def _recommendations(factor_scores: dict[str, int]) -> list[str]:
    recs = []
    if factor_scores["emi_burden"] >= 25:
        recs.append("Consider refinancing loans or reducing EMI obligations.")
    if factor_scores["volatility"] >= 18:
        recs.append("Set a monthly spending cap to reduce erratic withdrawals.")
    if factor_scores["liquidity"] >= 15:
        recs.append("Build an emergency fund covering at least 3 months of expenses.")
    if factor_scores["savings_rate"] >= 10:
        recs.append("Automate a fixed savings transfer on salary day.")
    if not recs:
        recs.append("Keep up the good work — maintain your current financial habits.")
    return recs


# ── Main scoring function ─────────────────────────────────────────────────────

def compute_risk_score(
    transactions: list[Transaction],
    emi_monthly: float = 0.0,
    current_balance: Optional[float] = None,
) -> RiskResult:
    """
    Compute an explainable risk score from transaction history.

    Args:
        transactions:    list of Transaction objects
        emi_monthly:     total fixed EMI/loan payments per month (if known)
        current_balance: current account balance (uses last transaction balance if None)

    Returns:
        RiskResult with score, label, factor breakdown, and explanations
    """
    expenses = [t for t in transactions if t.type == "Expense"]
    incomes  = [t for t in transactions if t.type == "Income"]

    # Monthly aggregates
    from collections import defaultdict
    monthly_exp: dict[str, float] = defaultdict(float)
    for t in expenses:
        monthly_exp[t.date.strftime("%Y-%m")] += abs(t.amount)

    monthly_expenses = list(monthly_exp.values())
    avg_monthly_expense = mean(monthly_expenses) if monthly_expenses else 0.0
    total_income = sum(abs(t.amount) for t in incomes)
    months = len(monthly_exp) or 1
    monthly_income = total_income / months

    # Resolve balance
    if current_balance is None:
        balances = [t.balance for t in transactions if t.balance is not None]
        current_balance = balances[-1] if balances else avg_monthly_expense * 2

    # Compute each factor
    emi_pts,  emi_ratio,  emi_msg  = _emi_burden_score(emi_monthly, monthly_income)
    vol_pts,  cv,         vol_msg  = _volatility_score(monthly_expenses)
    liq_pts,  days,       liq_msg  = _liquidity_score(current_balance, avg_monthly_expense)
    sav_pts,  sav_rate,   sav_msg  = _savings_score(monthly_income, avg_monthly_expense)

    total_score = min(100, emi_pts + vol_pts + liq_pts + sav_pts)

    return RiskResult(
        score=total_score,
        label=_label(total_score),
        factors={
            "emi_ratio":            round(emi_ratio, 3),
            "spending_cv":          round(cv, 3),
            "buffer_days":          round(days, 1),
            "savings_rate":         round(sav_rate, 3),
            "monthly_income":       round(monthly_income, 2),
            "avg_monthly_expense":  round(avg_monthly_expense, 2),
        },
        factor_scores={
            "emi_burden":   emi_pts,
            "volatility":   vol_pts,
            "liquidity":    liq_pts,
            "savings_rate": sav_pts,
        },
        explanations=[emi_msg, vol_msg, liq_msg, sav_msg],
        recommendations=_recommendations({
            "emi_burden":   emi_pts,
            "volatility":   vol_pts,
            "liquidity":    liq_pts,
            "savings_rate": sav_pts,
        }),
    )
