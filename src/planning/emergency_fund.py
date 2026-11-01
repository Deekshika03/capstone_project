"""
emergency_fund.py — Chunk 6
Emergency Fund Planner & Financial Actions

Responsibilities:
- Compute target emergency corpus (3–6 months of essential expenses,
  with extra buffer for senior citizen medical contingencies).
- Compare actual liquid savings against the target corpus.
- Generate personalized, actionable steps with specific amounts.
- Produce a structured savings milestone report given a user's expense profile.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional, Sequence, Union

import pandas as pd

from src.ingestion.transaction import Transaction


# ── Constants ─────────────────────────────────────────────────────────────────

ESSENTIAL_CATEGORIES = {
    "rent", "loan / emi", "emi", "insurance", "utility", "utilities",
    "bills", "groceries", "grocery", "food", "transport", "medical",
    "health", "education", "electricity", "water", "gas", "internet",
    "phone", "mobile",
}

DISCRETIONARY_CATEGORIES = {
    "entertainment", "shopping", "subscription", "dining", "restaurant",
    "travel", "gym", "gaming", "streaming", "other",
}

# Extra months added to 6-month corpus for senior citizens (medical buffer)
SENIOR_MEDICAL_BUFFER_MONTHS = 2


# ── Data Models ───────────────────────────────────────────────────────────────

@dataclass
class ExpenseProfile:
    """Summarised monthly expense breakdown derived from transaction history."""
    monthly_essential: float
    monthly_discretionary: float
    monthly_total: float
    monthly_income: float
    months_analysed: int
    category_breakdown: Dict[str, float] = field(default_factory=dict)
    flagged_subscriptions: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class EmergencyCorpus:
    """Target emergency fund corpus at different coverage levels."""
    target_3m: float
    target_6m: float
    target_senior: float        # 6m + senior medical buffer
    recommended_target: float
    coverage_months: float
    is_senior: bool


@dataclass
class FundGap:
    """Gap between current savings and the target corpus."""
    current_savings: float
    target: float
    gap: float          # positive = shortfall, negative = surplus
    pct_funded: float   # 0–100
    is_funded: bool


@dataclass
class ActionStep:
    """A single personalized, actionable recommendation."""
    priority: int
    action: str
    detail: str
    monthly_impact: float


@dataclass
class MilestoneReport:
    """Structured savings milestone report."""
    generated_on: date
    profile: ExpenseProfile
    corpus: EmergencyCorpus
    gap: FundGap
    monthly_savings_available: float
    planned_monthly_contribution: float
    months_to_3m_target: Optional[int]
    months_to_6m_target: Optional[int]
    months_to_recommended_target: Optional[int]
    milestones: List[Dict[str, Any]]
    action_steps: List[ActionStep]
    summary_lines: List[str]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _months_to_reach(gap: float, monthly: float) -> Optional[int]:
    if gap <= 0:
        return 0
    if monthly <= 0:
        return None
    return math.ceil(gap / monthly)


def _target_date(months: Optional[int], from_date: date) -> Optional[str]:
    if months is None:
        return None
    if months == 0:
        return "Already reached"
    m = from_date.month + months - 1
    y = from_date.year + m // 12
    mo = m % 12 + 1
    return date(y, mo, 1).strftime("%b %Y")


def _is_essential(category: str) -> bool:
    return category.strip().lower() in ESSENTIAL_CATEGORIES


def _is_discretionary(category: str) -> bool:
    return category.strip().lower() in DISCRETIONARY_CATEGORIES


def _detect_duplicate_subscriptions(
    transactions: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Flag subscription/entertainment transactions as potential cuts."""
    sub_txs = [
        t for t in transactions
        if t.get("category", "").strip().lower() in
        ("subscription", "entertainment", "streaming", "bills")
    ]
    seen: set = set()
    flagged = []
    for t in sub_txs:
        name = t.get("description", "Unknown")
        amt  = abs(t.get("amount", 0.0))
        key  = (name.lower()[:20], round(amt, 0))
        if key not in seen:
            seen.add(key)
            flagged.append({"name": name, "amount": amt})
    return flagged


# ── Core Functions ────────────────────────────────────────────────────────────

def build_expense_profile(
    transactions: Union[Sequence[Transaction], pd.DataFrame, Sequence[Dict[str, Any]]],
) -> ExpenseProfile:
    """
    Derive a monthly expense profile from transaction history.
    Accepts Transaction objects, a DataFrame, or list of dicts.
    """
    records: List[Dict[str, Any]] = []

    if isinstance(transactions, pd.DataFrame):
        if transactions.empty:
            return ExpenseProfile(0, 0, 0, 0, 0)
        col_map = {str(c).lower(): c for c in transactions.columns}
        for _, row in transactions.iterrows():
            amt_raw = row.get(col_map.get("amount", "Amount"), 0)
            if pd.isna(amt_raw):
                continue
            d = row.get(col_map.get("date", "Date"))
            if pd.isna(d):
                continue
            records.append({
                "date":        pd.to_datetime(d).date(),
                "description": str(row.get(col_map.get("description", "Description"), "Unknown")),
                "amount":      float(amt_raw),
                "type":        str(row.get(col_map.get("type", "Type"), "Expense")).capitalize(),
                "category":    str(row.get(col_map.get("category", "Category"), "Other")),
            })
    else:
        for item in transactions:
            if isinstance(item, Transaction):
                records.append({
                    "date":        item.date,
                    "description": item.description,
                    "amount":      item.amount,
                    "type":        item.type,
                    "category":    item.category or "Other",
                })
            elif isinstance(item, dict):
                records.append({
                    "date":        item.get("date", item.get("Date")),
                    "description": str(item.get("description", item.get("Description", "Unknown"))),
                    "amount":      float(item.get("amount", item.get("Amount", 0))),
                    "type":        str(item.get("type", item.get("Type", "Expense"))).capitalize(),
                    "category":    str(item.get("category", item.get("Category", "Other"))),
                })

    if not records:
        return ExpenseProfile(0, 0, 0, 0, 0)

    expenses = [r for r in records if r["type"] == "Expense" and abs(r["amount"]) > 0]
    incomes  = [r for r in records if r["type"] == "Income"  and abs(r["amount"]) > 0]

    all_months   = {str(r["date"])[:7] for r in records}
    months_count = max(len(all_months), 1)

    cat_totals: Dict[str, float] = {}
    for e in expenses:
        cat = e["category"]
        cat_totals[cat] = cat_totals.get(cat, 0.0) + abs(e["amount"])

    monthly_essential     = sum(v for k, v in cat_totals.items() if _is_essential(k))     / months_count
    monthly_discretionary = sum(v for k, v in cat_totals.items() if _is_discretionary(k)) / months_count
    monthly_total         = sum(cat_totals.values()) / months_count
    monthly_income        = sum(abs(i["amount"]) for i in incomes) / months_count
    monthly_breakdown     = {k: round(v / months_count, 2) for k, v in cat_totals.items()}
    flagged_subs          = _detect_duplicate_subscriptions(expenses)

    return ExpenseProfile(
        monthly_essential=round(monthly_essential, 2),
        monthly_discretionary=round(monthly_discretionary, 2),
        monthly_total=round(monthly_total, 2),
        monthly_income=round(monthly_income, 2),
        months_analysed=months_count,
        category_breakdown=monthly_breakdown,
        flagged_subscriptions=flagged_subs,
    )


def compute_emergency_corpus(
    profile: ExpenseProfile,
    is_senior: bool = False,
    custom_monthly_essential: Optional[float] = None,
) -> EmergencyCorpus:
    """
    Compute the target emergency corpus.

    - 3-month target  : minimum safety net
    - 6-month target  : recommended for most users
    - Senior target   : 6m + 2-month medical buffer for senior citizens
    """
    essential = custom_monthly_essential if custom_monthly_essential is not None \
        else profile.monthly_essential

    # Fallback: if no categorised essential data, use 50% of total spend
    if essential <= 0:
        essential = profile.monthly_total * 0.5

    target_3m     = round(essential * 3, 2)
    target_6m     = round(essential * 6, 2)
    target_senior = round(essential * (6 + SENIOR_MEDICAL_BUFFER_MONTHS), 2)
    recommended   = target_senior if is_senior else target_6m
    coverage      = float(6 + SENIOR_MEDICAL_BUFFER_MONTHS) if is_senior else 6.0

    return EmergencyCorpus(
        target_3m=target_3m,
        target_6m=target_6m,
        target_senior=target_senior,
        recommended_target=recommended,
        coverage_months=coverage,
        is_senior=is_senior,
    )


def analyse_fund_gap(corpus: EmergencyCorpus, current_savings: float) -> FundGap:
    """Compare current liquid savings against the recommended corpus target."""
    gap       = corpus.recommended_target - current_savings
    pct       = min((current_savings / corpus.recommended_target) * 100, 100.0) \
                if corpus.recommended_target > 0 else 100.0
    is_funded = current_savings >= corpus.recommended_target

    return FundGap(
        current_savings=round(current_savings, 2),
        target=corpus.recommended_target,
        gap=round(gap, 2),
        pct_funded=round(pct, 1),
        is_funded=is_funded,
    )


def generate_action_steps(
    profile: ExpenseProfile,
    gap: FundGap,
    planned_monthly_contribution: float,
    currency: str = "₹",
) -> List[ActionStep]:
    """
    Generate personalized, actionable steps to close the emergency fund gap.
    Each step includes a specific monetary amount and projected timeline.
    """
    steps: List[ActionStep] = []
    p = 1

    if gap.is_funded:
        steps.append(ActionStep(
            priority=p,
            action="Maintain & Invest Surplus",
            detail=(
                f"Your emergency fund is fully funded ({gap.pct_funded:.1f}% of target). "
                f"Consider investing the surplus {currency}{abs(gap.gap):,.0f} "
                f"in liquid mutual funds or high-yield FDs."
            ),
            monthly_impact=0.0,
        ))
        return steps

    contribution = max(planned_monthly_contribution, 0.0)
    m_rec = _months_to_reach(gap.gap, contribution)

    # Step 1 — Direct monthly allocation
    steps.append(ActionStep(
        priority=p,
        action="Set Up Automatic Monthly Transfer",
        detail=(
            f"Allocate {currency}{contribution:,.0f}/month to your emergency fund. "
            f"At this rate you will reach your {currency}{gap.target:,.0f} target "
            f"in {m_rec} month(s) ({_target_date(m_rec, date.today())})."
            if m_rec else
            f"Set a monthly contribution to start building your {currency}{gap.target:,.0f} corpus."
        ),
        monthly_impact=contribution,
    ))
    p += 1

    # Step 2 — Cut flagged subscriptions
    if profile.flagged_subscriptions:
        total_sub  = sum(s["amount"] for s in profile.flagged_subscriptions)
        sub_names  = ", ".join(s["name"] for s in profile.flagged_subscriptions[:3])
        new_months = _months_to_reach(gap.gap, contribution + total_sub)
        steps.append(ActionStep(
            priority=p,
            action="Cancel Duplicate / Unused Subscriptions",
            detail=(
                f"Flagged subscriptions ({sub_names}) total {currency}{total_sub:,.0f}/month. "
                f"Redirecting this to your emergency fund reduces the timeline to "
                f"{new_months} month(s) ({_target_date(new_months, date.today())})."
            ),
            monthly_impact=total_sub,
        ))
        p += 1

    # Step 3 — Reduce discretionary spending by 20%
    if profile.monthly_discretionary > 0:
        cut        = round(profile.monthly_discretionary * 0.20, 2)
        new_months = _months_to_reach(gap.gap, contribution + cut)
        steps.append(ActionStep(
            priority=p,
            action="Reduce Discretionary Spending by 20%",
            detail=(
                f"Your average discretionary spend is {currency}{profile.monthly_discretionary:,.0f}/month. "
                f"A 20% cut frees up {currency}{cut:,.0f}/month, "
                f"shortening the timeline to {new_months} month(s)."
            ),
            monthly_impact=cut,
        ))
        p += 1

    # Step 4 — Park in liquid instrument
    steps.append(ActionStep(
        priority=p,
        action="Park Fund in a Liquid Instrument",
        detail=(
            "Keep your emergency corpus in a high-yield savings account or liquid mutual fund "
            "(not locked FDs) so it earns returns while remaining accessible within 1–2 business days."
        ),
        monthly_impact=0.0,
    ))
    p += 1

    # Step 5 — Review essential load if it dominates income
    if profile.monthly_income > 0 and profile.monthly_essential > profile.monthly_income * 0.70:
        steps.append(ActionStep(
            priority=p,
            action="Review Essential Expense Load",
            detail=(
                f"Essential expenses ({currency}{profile.monthly_essential:,.0f}/month) consume "
                f"{profile.monthly_essential / profile.monthly_income * 100:.0f}% of income. "
                f"Consider refinancing loans or renegotiating rent to free up cash flow."
            ),
            monthly_impact=0.0,
        ))

    return steps


def generate_milestone_report(
    transactions: Union[Sequence[Transaction], pd.DataFrame, Sequence[Dict[str, Any]]],
    current_savings: float,
    planned_monthly_contribution: float,
    is_senior: bool = False,
    custom_monthly_essential: Optional[float] = None,
    currency: str = "₹",
    as_of: Optional[date] = None,
) -> MilestoneReport:
    """
    Produce a complete structured savings milestone report.

    Parameters
    ----------
    transactions                 : historical transaction data (any supported format)
    current_savings              : current liquid savings / emergency fund balance
    planned_monthly_contribution : amount user plans to save each month
    is_senior                    : True adds a 2-month medical buffer to the corpus
    custom_monthly_essential     : override auto-detected essential expenses
    currency                     : symbol for display (default ₹)
    as_of                        : reference date (defaults to today)
    """
    if as_of is None:
        as_of = date.today()

    profile = build_expense_profile(transactions)
    corpus  = compute_emergency_corpus(
        profile, is_senior=is_senior,
        custom_monthly_essential=custom_monthly_essential,
    )
    gap         = analyse_fund_gap(corpus, current_savings)
    contribution = max(planned_monthly_contribution, 0.0)

    monthly_savings_available = max(profile.monthly_income - profile.monthly_total, 0.0)

    # Per-milestone gap & timeline
    gap_3m  = max(corpus.target_3m  - current_savings, 0)
    gap_6m  = max(corpus.target_6m  - current_savings, 0)
    gap_rec = max(corpus.recommended_target - current_savings, 0)

    m_3m  = _months_to_reach(gap_3m,  contribution)
    m_6m  = _months_to_reach(gap_6m,  contribution)
    m_rec = _months_to_reach(gap_rec, contribution)

    def _pct(target):
        return round(min(current_savings / target * 100, 100), 1) if target > 0 else 100.0

    milestones = [
        {
            "label":       "3-Month Safety Net",
            "target":      corpus.target_3m,
            "gap":         gap_3m,
            "months":      m_3m,
            "target_date": _target_date(m_3m, as_of),
            "pct_funded":  _pct(corpus.target_3m),
        },
        {
            "label":       "6-Month Recommended Fund",
            "target":      corpus.target_6m,
            "gap":         gap_6m,
            "months":      m_6m,
            "target_date": _target_date(m_6m, as_of),
            "pct_funded":  _pct(corpus.target_6m),
        },
    ]
    if is_senior:
        gap_sr = max(corpus.target_senior - current_savings, 0)
        m_sr   = _months_to_reach(gap_sr, contribution)
        milestones.append({
            "label":       f"Senior Citizen Medical Buffer ({6 + SENIOR_MEDICAL_BUFFER_MONTHS}-Month)",
            "target":      corpus.target_senior,
            "gap":         gap_sr,
            "months":      m_sr,
            "target_date": _target_date(m_sr, as_of),
            "pct_funded":  _pct(corpus.target_senior),
        })

    action_steps = generate_action_steps(profile, gap, contribution, currency=currency)

    # Human-readable summary bullets
    summary: List[str] = [
        f"Monthly essential expenses: {currency}{profile.monthly_essential:,.0f} | "
        f"Discretionary: {currency}{profile.monthly_discretionary:,.0f}",
        f"Recommended emergency corpus ({corpus.coverage_months:.0f} months): "
        f"{currency}{corpus.recommended_target:,.0f}",
        f"Current savings: {currency}{current_savings:,.0f} — "
        + (
            "✅ Fully funded!"
            if gap.is_funded else
            f"Shortfall: {currency}{gap.gap:,.0f} ({gap.pct_funded:.1f}% funded)"
        ),
    ]
    if not gap.is_funded and m_rec is not None:
        summary.append(
            f"At {currency}{contribution:,.0f}/month → reach target in "
            f"{m_rec} month(s) ({_target_date(m_rec, as_of)})"
        )
    if profile.flagged_subscriptions:
        total_sub = sum(s["amount"] for s in profile.flagged_subscriptions)
        summary.append(
            f"⚠️ {len(profile.flagged_subscriptions)} subscription(s) flagged totalling "
            f"{currency}{total_sub:,.0f}/month — review for cuts."
        )

    return MilestoneReport(
        generated_on=as_of,
        profile=profile,
        corpus=corpus,
        gap=gap,
        monthly_savings_available=round(monthly_savings_available, 2),
        planned_monthly_contribution=contribution,
        months_to_3m_target=m_3m,
        months_to_6m_target=m_6m,
        months_to_recommended_target=m_rec,
        milestones=milestones,
        action_steps=action_steps,
        summary_lines=summary,
    )
