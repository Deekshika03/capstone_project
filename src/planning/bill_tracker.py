"""
bill_tracker.py — Chunk 4
Recurring Bills, EMI Detector & Alert System

Responsibilities:
- Identify recurring transactions based on frequency and similar amounts (e.g., monthly loan EMIs, rent, insurance premiums).
- Calculate upcoming payment due dates and projected cash outflows for the next 30 days.
- Generate priority alerts (e.g., “High EMI due in 4 days. Projected balance may be insufficient”).
- Produce an alert list sorted by urgency.
"""

from __future__ import annotations

import calendar
import re
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import pandas as pd
from pydantic import BaseModel, Field

from src.ingestion.transaction import Transaction


class BillCategory(str, Enum):
    EMI_LOAN = "Loan / EMI"
    RENT = "Rent"
    INSURANCE = "Insurance"
    UTILITY = "Utility"
    SUBSCRIPTION = "Subscription"
    OTHER = "Other"


class AlertPriority(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class RecurringBill(BaseModel):
    name: str = Field(description="Name or merchant of recurring bill/EMI")
    category: str = Field(default=BillCategory.OTHER.value, description="Identified category")
    expected_amount: float = Field(description="Expected or average outflow amount (positive)")
    frequency: str = Field(default="monthly", description="Frequency: monthly, weekly, biweekly, quarterly, annual")
    interval_days: float = Field(description="Average interval between payments in days")
    last_payment_date: date = Field(description="Date of the most recent recorded payment")
    next_due_date: date = Field(description="Estimated next due date")
    payment_count: int = Field(description="Number of detected historical occurrences")
    is_emi: bool = Field(default=False, description="Whether this recurring bill is a loan/EMI")
    confidence_score: float = Field(default=1.0, description="Confidence score between 0.0 and 1.0")
    historical_dates: List[date] = Field(default_factory=list, description="Past payment dates")
    historical_amounts: List[float] = Field(default_factory=list, description="Past payment amounts")


class UpcomingPayment(BaseModel):
    bill_name: str
    category: str
    amount: float
    due_date: date
    days_until_due: int
    is_emi: bool
    urgency_status: str


class BillAlert(BaseModel):
    title: str
    message: str
    priority: AlertPriority
    urgency_score: int = Field(
        ge=0, le=100, description="Urgency score from 0 (lowest) to 100 (highest)"
    )
    due_date: Optional[date] = None
    days_until_due: Optional[int] = None
    amount: Optional[float] = None
    is_emi: bool = False
    alert_type: str = "general"


class CashOutflowProjection(BaseModel):
    as_of_date: date
    projection_window_days: int = 30
    total_projected_outflow: float = 0.0
    total_emi_outflow: float = 0.0
    total_non_emi_outflow: float = 0.0
    total_bills_count: int = 0
    upcoming_payments: List[UpcomingPayment] = Field(default_factory=list)
    daily_outflows: Dict[str, float] = Field(default_factory=dict)


# ── Regex Patterns for Categorization & EMI Detection ────────────────────────

_EMI_REGEX = re.compile(
    r"\b(emi|loan|mortgage|car\s+loan|home\s+loan|auto\s+loan|personal\s+loan|"
    r"education\s+loan|equated\s+monthly|repayment|financing|housing\s+loan|"
    r"vehicle\s+loan|term\s+loan)\b",
    re.IGNORECASE,
)

_RENT_REGEX = re.compile(
    r"\b(rent|lease|landlord|flat\s+rent|apartment\s+rent|housing\s+society|"
    r"maintenance\s+fee|condo\s+fee)\b",
    re.IGNORECASE,
)

_INSURANCE_REGEX = re.compile(
    r"\b(insurance|lic|policy|premium|mediclaim|health\s+insurance|"
    r"car\s+insurance|life\s+insurance|term\s+plan)\b",
    re.IGNORECASE,
)

_UTILITY_REGEX = re.compile(
    r"\b(bill|electric|electricity|water|gas|utility|internet|broadband|"
    r"wifi|phone|mobile|postpaid|sewer|trash|power)\b",
    re.IGNORECASE,
)

_SUBSCRIPTION_REGEX = re.compile(
    r"\b(subscription|netflix|spotify|prime|amazon\s+prime|disney|hulu|"
    r"gym|membership|cloud|apple|icloud|chatgpt|youtube|adobe)\b",
    re.IGNORECASE,
)

_FINANCIAL_INSTITUTIONS_REGEX = re.compile(
    r"\b(hdfc|sbi|icici|chase|citi|wells\s+fargo|bank|capital|finance|"
    r"credit\s+union|barclays|hsbc|axis|kotak)\b",
    re.IGNORECASE,
)


# ── Helpers for Normalization & Dates ─────────────────────────────────────────

def _to_date(val: Any) -> date:
    """Coerce string, datetime, Timestamp, or date to date."""
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, pd.Timestamp):
        return val.date()
    if isinstance(val, str):
        cleaned = val.strip()
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(cleaned, fmt).date()
            except ValueError:
                pass
        return pd.to_datetime(cleaned).date()
    raise ValueError(f"Cannot parse date from: {val!r}")


def _add_months(d: date, months: int) -> date:
    """Add `months` to `d`, preserving day-of-month and handling month length."""
    new_year = d.year + (d.month - 1 + months) // 12
    new_month = (d.month - 1 + months) % 12 + 1
    max_days = calendar.monthrange(new_year, new_month)[1]
    new_day = min(d.day, max_days)
    return date(new_year, new_month, new_day)


def _clean_description(desc: str) -> str:
    """Clean transaction description to extract a merchant/purpose signature."""
    s = str(desc).strip().lower()
    # Remove reference numbers / transaction IDs
    s = re.sub(r"(ref|txn|id|tx|num|no)[:#]?\s*[\w\d]+", "", s)
    s = re.sub(r"\b[0-9a-f]{8,}\b", "", s)
    s = re.sub(r"\b\d{5,}\b", "", s)
    # Remove dates
    s = re.sub(r"\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b", "", s)
    s = re.sub(r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b", "", s)
    s = re.sub(
        r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\b",
        "",
        s,
    )
    s = re.sub(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b", "", s)
    # Remove banking transaction noise terms
    s = re.sub(r"\b(pos|ach|neft|rtgs|imps|upi|auto[- ]?debit|standing[- ]?instruction|direct[- ]?debit)\b", "", s)
    # Remove punctuation
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s or str(desc).strip().lower()


def _infer_category_and_emi(description: str, amount: float = 0.0) -> Tuple[str, bool]:
    """Classify recurring bill category and determine whether it is a loan/EMI."""
    desc = description.strip()

    # 1. Exact EMI / Loan match
    if _EMI_REGEX.search(desc):
        return BillCategory.EMI_LOAN.value, True

    # 2. Rent match
    if _RENT_REGEX.search(desc):
        return BillCategory.RENT.value, False

    # 3. Insurance match
    if _INSURANCE_REGEX.search(desc):
        return BillCategory.INSURANCE.value, False

    # 4. Utility match
    if _UTILITY_REGEX.search(desc):
        return BillCategory.UTILITY.value, False

    # 5. Subscription match
    if _SUBSCRIPTION_REGEX.search(desc):
        return BillCategory.SUBSCRIPTION.value, False

    # 6. Financial institution name with regular significant recurring payment
    if _FINANCIAL_INSTITUTIONS_REGEX.search(desc) and amount >= 250.0:
        return BillCategory.EMI_LOAN.value, True

    return BillCategory.OTHER.value, False


def _standardize_transactions(
    records: Union[Sequence[Transaction], pd.DataFrame, Sequence[Dict[str, Any]]]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Normalize input into (expenses, incomes) records.
    Returns:
    - expenses: list of dicts with date, description, amount, type='Expense'
    - incomes: list of dicts with date, description, amount, type='Income'
    """
    expenses: List[Dict[str, Any]] = []
    incomes: List[Dict[str, Any]] = []

    if isinstance(records, pd.DataFrame):
        if records.empty:
            return [], []
        df = records.copy()
        col_map = {str(c).lower(): c for c in df.columns}
        date_col = col_map.get("date")
        desc_col = col_map.get("description")
        amt_col = col_map.get("amount")
        type_col = col_map.get("type")

        if not (date_col and desc_col and amt_col):
            raise ValueError(
                f"DataFrame must contain 'Date', 'Description', and 'Amount' columns. Found: {list(df.columns)}"
            )

        for _, row in df.iterrows():
            d_val = row[date_col]
            if pd.isna(d_val):
                continue
            desc = str(row[desc_col]) if not pd.isna(row[desc_col]) else "Unknown"
            amt_raw = row[amt_col]
            if pd.isna(amt_raw):
                continue
            amt = float(amt_raw)
            tx_type = str(row[type_col]).strip().capitalize() if type_col and not pd.isna(row[type_col]) else None

            try:
                d = _to_date(d_val)
            except Exception:
                continue

            if tx_type == "Income" or (tx_type is None and amt > 0 and "salary" in desc.lower()):
                incomes.append({"date": d, "description": desc, "amount": abs(amt), "type": "Income"})
            else:
                outflow = abs(amt)
                if outflow > 0:
                    expenses.append({"date": d, "description": desc, "amount": outflow, "type": "Expense"})

    elif isinstance(records, Sequence):
        for item in records:
            if isinstance(item, Transaction):
                if item.type.lower() == "income":
                    incomes.append({
                        "date": item.date,
                        "description": item.description,
                        "amount": abs(item.amount),
                        "type": "Income",
                    })
                else:
                    outflow = abs(item.amount)
                    if outflow > 0:
                        expenses.append({
                            "date": item.date,
                            "description": item.description,
                            "amount": outflow,
                            "type": "Expense",
                        })
            elif isinstance(item, dict):
                tx_type = str(item.get("type", item.get("Type", ""))).strip().capitalize()
                amt_raw = item.get("amount", item.get("Amount", 0.0))
                amt = float(amt_raw)
                d_val = item.get("date", item.get("Date"))
                desc = str(item.get("description", item.get("Description", "Unknown")))
                try:
                    d = _to_date(d_val)
                except Exception:
                    continue

                if tx_type == "Income" or (amt > 0 and "salary" in desc.lower()):
                    incomes.append({"date": d, "description": desc, "amount": abs(amt), "type": "Income"})
                else:
                    outflow = abs(amt)
                    if outflow > 0:
                        expenses.append({"date": d, "description": desc, "amount": outflow, "type": "Expense"})
            else:
                raise TypeError(f"Unsupported transaction element type: {type(item)}")

    return expenses, incomes


# ── Core Recurring Bill & EMI Detection ───────────────────────────────────────

def detect_recurring_bills(
    transactions: Union[Sequence[Transaction], pd.DataFrame, Sequence[Dict[str, Any]]],
    amount_tolerance: float = 0.15,
    min_occurrences: int = 2,
    as_of_date: Optional[date] = None,
) -> List[RecurringBill]:
    """
    Identify recurring bills and EMIs based on frequency and similar amounts.

    Parameters
    ----------
    transactions : list of Transaction, DataFrame, or list of dicts.
    amount_tolerance : maximum fractional difference in amount within a recurring series (default 0.15).
    min_occurrences : minimum number of historical occurrences to qualify as recurring (default 2).
    as_of_date : reference date for next due date projection (defaults to latest date or today).

    Returns
    -------
    List[RecurringBill] sorted by next_due_date.
    """
    expenses, _ = _standardize_transactions(transactions)
    if not expenses:
        return []

    expenses.sort(key=lambda x: x["date"])

    if as_of_date is None:
        as_of_date = max(x["date"] for x in expenses)

    # Step 1: Group by normalized merchant signature
    grouped_by_merchant: Dict[str, List[Dict[str, Any]]] = {}
    display_names: Dict[str, str] = {}

    for tx in expenses:
        cleaned = _clean_description(tx["description"])
        matched_key = None
        for existing_key in grouped_by_merchant.keys():
            if existing_key == cleaned:
                matched_key = existing_key
                break
            ratio = SequenceMatcher(None, existing_key, cleaned).ratio()
            if ratio >= 0.80:
                matched_key = existing_key
                break

        if matched_key:
            grouped_by_merchant[matched_key].append(tx)
        else:
            grouped_by_merchant[cleaned] = [tx]
            display_names[cleaned] = tx["description"]

    detected_bills: List[RecurringBill] = []

    # Step 2: For each merchant group, cluster by amount similarity
    for group_key, tx_list in grouped_by_merchant.items():
        if len(tx_list) < min_occurrences:
            continue

        tx_list.sort(key=lambda x: x["date"])

        amount_clusters: List[List[Dict[str, Any]]] = []
        for tx in tx_list:
            placed = False
            for cluster in amount_clusters:
                avg_cluster_amt = sum(c["amount"] for c in cluster) / len(cluster)
                diff = abs(tx["amount"] - avg_cluster_amt)
                rel_diff = diff / avg_cluster_amt if avg_cluster_amt > 0 else 0
                if rel_diff <= amount_tolerance:
                    cluster.append(tx)
                    placed = True
                    break
            if not placed:
                amount_clusters.append([tx])

        # Step 3: Analyze interval & frequency for each cluster
        for cluster in amount_clusters:
            if len(cluster) < min_occurrences:
                continue

            cluster.sort(key=lambda x: x["date"])
            dates = [c["date"] for c in cluster]
            amounts = [c["amount"] for c in cluster]

            # Calculate intervals in days between consecutive dates
            intervals: List[int] = []
            for i in range(len(dates) - 1):
                diff_days = (dates[i + 1] - dates[i]).days
                if diff_days > 0:
                    intervals.append(diff_days)

            if not intervals:
                continue

            avg_interval = sum(intervals) / len(intervals)
            sorted_intervals = sorted(intervals)
            median_interval = sorted_intervals[len(sorted_intervals) // 2]

            # Determine frequency
            frequency: Optional[str] = None
            if 5 <= median_interval <= 9:
                frequency = "weekly"
            elif 12 <= median_interval <= 17:
                frequency = "biweekly"
            elif 25 <= median_interval <= 35:
                frequency = "monthly"
            elif 75 <= median_interval <= 105:
                frequency = "quarterly"
            elif 340 <= median_interval <= 380:
                frequency = "annual"
            else:
                if 24 <= avg_interval <= 36:
                    frequency = "monthly"

            if not frequency:
                continue

            # Compute regularity/confidence score
            if len(intervals) > 1:
                interval_var = sum((x - avg_interval) ** 2 for x in intervals) / len(intervals)
                interval_std = interval_var ** 0.5
            else:
                interval_std = 0.0

            avg_amount = sum(amounts) / len(amounts)
            if len(amounts) > 1:
                amt_var = sum((a - avg_amount) ** 2 for a in amounts) / len(amounts)
                amt_std = amt_var ** 0.5
            else:
                amt_std = 0.0

            interval_consistency = max(0.0, 1.0 - min(interval_std / 15.0, 0.5))
            amount_consistency = max(0.0, 1.0 - min(amt_std / (avg_amount + 1e-6), 0.5))
            confidence = round(interval_consistency * 0.6 + amount_consistency * 0.4, 2)

            name = display_names.get(group_key, cluster[0]["description"])
            category, is_emi = _infer_category_and_emi(name, avg_amount)

            # High-consistency fixed monthly amount >= $250 with banking keywords
            if not is_emi and frequency == "monthly" and amt_std <= (avg_amount * 0.02) and avg_amount >= 250.0:
                if _FINANCIAL_INSTITUTIONS_REGEX.search(name):
                    category = BillCategory.EMI_LOAN.value
                    is_emi = True

            last_payment = dates[-1]
            next_due = _compute_next_due_date(last_payment, frequency, as_of_date)

            bill = RecurringBill(
                name=name,
                category=category,
                expected_amount=round(avg_amount, 2),
                frequency=frequency,
                interval_days=round(avg_interval, 1),
                last_payment_date=last_payment,
                next_due_date=next_due,
                payment_count=len(cluster),
                is_emi=is_emi,
                confidence_score=confidence,
                historical_dates=dates,
                historical_amounts=[round(a, 2) for a in amounts],
            )
            detected_bills.append(bill)

    detected_bills.sort(key=lambda b: (b.next_due_date, -b.expected_amount))
    return detected_bills


def _compute_next_due_date(last_payment: date, frequency: str, as_of_date: date) -> date:
    """Project the next payment due date from last_payment relative to as_of_date."""
    candidate = last_payment

    def _step(cur: date) -> date:
        if frequency == "weekly":
            return cur + timedelta(days=7)
        if frequency == "biweekly":
            return cur + timedelta(days=14)
        if frequency == "monthly":
            return _add_months(cur, 1)
        if frequency == "quarterly":
            return _add_months(cur, 3)
        if frequency == "annual":
            return _add_months(cur, 12)
        return cur + timedelta(days=30)

    # Step forward until candidate is on or after as_of_date
    while candidate < as_of_date:
        candidate = _step(candidate)

    return candidate


# ── Calculate Upcoming Payments & 30-Day Cash Outflows ────────────────────────

def calculate_upcoming_payments(
    bills: Sequence[RecurringBill],
    as_of_date: Optional[date] = None,
    days_ahead: int = 30,
) -> List[UpcomingPayment]:
    """
    Calculate upcoming payments due within the next `days_ahead` days (default 30 days).

    Parameters
    ----------
    bills : list of RecurringBill.
    as_of_date : start date of projection window.
    days_ahead : projection window size in days (default 30).

    Returns
    -------
    List[UpcomingPayment] sorted by due_date ascending.
    """
    if as_of_date is None:
        if bills:
            as_of_date = max(b.last_payment_date for b in bills)
        else:
            as_of_date = date.today()

    end_date = as_of_date + timedelta(days=days_ahead)
    upcoming: List[UpcomingPayment] = []

    for bill in bills:
        cur_due = bill.next_due_date
        if cur_due < as_of_date:
            cur_due = _compute_next_due_date(bill.last_payment_date, bill.frequency, as_of_date)

        while cur_due <= end_date:
            days_left = (cur_due - as_of_date).days

            if days_left < 0:
                status = "Overdue"
            elif days_left == 0:
                status = "Due Today"
            elif days_left <= 3:
                status = "Due Soon (1-3 days)"
            elif days_left <= 7:
                status = "Due this week"
            else:
                status = "Upcoming"

            upcoming.append(
                UpcomingPayment(
                    bill_name=bill.name,
                    category=bill.category,
                    amount=bill.expected_amount,
                    due_date=cur_due,
                    days_until_due=days_left,
                    is_emi=bill.is_emi,
                    urgency_status=status,
                )
            )

            # Advance to next cycle
            if bill.frequency == "weekly":
                cur_due = cur_due + timedelta(days=7)
            elif bill.frequency == "biweekly":
                cur_due = cur_due + timedelta(days=14)
            elif bill.frequency == "monthly":
                cur_due = _add_months(cur_due, 1)
            elif bill.frequency == "quarterly":
                cur_due = _add_months(cur_due, 3)
            elif bill.frequency == "annual":
                cur_due = _add_months(cur_due, 12)
            else:
                break

    upcoming.sort(key=lambda p: (p.due_date, -p.amount))
    return upcoming


def calculate_projected_cash_outflow(
    bills_or_payments: Union[Sequence[RecurringBill], Sequence[UpcomingPayment]],
    as_of_date: Optional[date] = None,
    days_ahead: int = 30,
) -> CashOutflowProjection:
    """
    Calculate projected cash outflows for the next 30 days.

    Parameters
    ----------
    bills_or_payments : list of RecurringBill or list of UpcomingPayment.
    as_of_date : reference date for projection.
    days_ahead : projection window (default 30 days).

    Returns
    -------
    CashOutflowProjection containing total outflow, EMI outflow, daily breakdown, and payments.
    """
    if as_of_date is None:
        as_of_date = date.today()

    if bills_or_payments and isinstance(bills_or_payments[0], RecurringBill):
        payments = calculate_upcoming_payments(
            bills_or_payments, as_of_date=as_of_date, days_ahead=days_ahead  # type: ignore
        )
    else:
        payments = list(bills_or_payments)  # type: ignore

    total_outflow = sum(p.amount for p in payments)
    emi_outflow = sum(p.amount for p in payments if p.is_emi)
    non_emi_outflow = total_outflow - emi_outflow

    daily_map: Dict[str, float] = {}
    for p in payments:
        k = p.due_date.isoformat()
        daily_map[k] = round(daily_map.get(k, 0.0) + p.amount, 2)

    return CashOutflowProjection(
        as_of_date=as_of_date,
        projection_window_days=days_ahead,
        total_projected_outflow=round(total_outflow, 2),
        total_emi_outflow=round(emi_outflow, 2),
        total_non_emi_outflow=round(non_emi_outflow, 2),
        total_bills_count=len(payments),
        upcoming_payments=payments,
        daily_outflows=daily_map,
    )


# ── Priority Alert Generation System ──────────────────────────────────────────

def generate_priority_alerts(
    upcoming_payments: Sequence[UpcomingPayment],
    current_balance: Optional[float] = None,
    monthly_income: Optional[float] = None,
    high_emi_amount_threshold: float = 300.0,
) -> List[BillAlert]:
    """
    Generate priority alerts sorted by urgency.

    Handles:
    - Insufficient projected balance for high EMIs and upcoming bills.
    - Imminent EMIs (e.g. "High EMI due in 4 days").
    - Overdue payments.
    - Regular bills due within 7 days.
    - Cash outflow warnings when 30-day outflows exceed current balance.

    Parameters
    ----------
    upcoming_payments : list of UpcomingPayment.
    current_balance : current available cash balance.
    monthly_income : optional monthly income for ratio checks.
    high_emi_amount_threshold : threshold to treat an EMI as "High EMI" (default $300).

    Returns
    -------
    List[BillAlert] sorted by urgency_score descending.
    """
    alerts: List[BillAlert] = []
    payments_sorted = sorted(upcoming_payments, key=lambda p: (p.due_date, -p.amount))

    # Track running projected balance
    running_balance = current_balance

    total_outflow = sum(p.amount for p in payments_sorted)

    # 1. Cumulative cash flow warning vs current balance
    if current_balance is not None and total_outflow > current_balance:
        shortfall = total_outflow - current_balance
        alerts.append(
            BillAlert(
                title="🚨 Cash Flow Deficit Warning",
                message=(
                    f"Projected 30-day outflow of ${total_outflow:,.2f} exceeds current balance "
                    f"(${current_balance:,.2f}) by ${shortfall:,.2f}."
                ),
                priority=AlertPriority.HIGH,
                urgency_score=88,
                amount=shortfall,
                alert_type="cash_flow_deficit",
            )
        )

    # 2. Per-payment alert evaluation
    for p in payments_sorted:
        days = p.days_until_due
        is_high_val = p.amount >= high_emi_amount_threshold

        # Update running balance
        insufficient_for_this = False
        projected_after = None
        if running_balance is not None:
            running_balance -= p.amount
            projected_after = running_balance
            if projected_after < 0:
                insufficient_for_this = True

        # CASE A: Overdue
        if days < 0:
            urgency = 98
            alerts.append(
                BillAlert(
                    title=f"🚨 Overdue: {p.bill_name}",
                    message=(
                        f"Payment of ${p.amount:,.2f} for '{p.bill_name}' was due on "
                        f"{p.due_date} ({abs(days)} day(s) ago). Please verify immediately."
                    ),
                    priority=AlertPriority.CRITICAL,
                    urgency_score=urgency,
                    due_date=p.due_date,
                    days_until_due=days,
                    amount=p.amount,
                    is_emi=p.is_emi,
                    alert_type="overdue",
                )
            )
            continue

        # CASE B: Projected Balance May Be Insufficient (CRITICAL)
        if insufficient_for_this:
            urgency = max(86, 96 - min(days, 10))
            if p.is_emi:
                msg = (
                    f"High EMI of ${p.amount:,.2f} for '{p.bill_name}' due in {days} day(s) "
                    f"({p.due_date}). Projected balance (${projected_after:,.2f}) may be insufficient!"
                )
            else:
                msg = (
                    f"Upcoming payment of ${p.amount:,.2f} for '{p.bill_name}' due in {days} day(s) "
                    f"({p.due_date}). Projected balance (${projected_after:,.2f}) may be insufficient!"
                )

            alerts.append(
                BillAlert(
                    title=f"🚨 Insufficient Balance for {p.bill_name}",
                    message=msg,
                    priority=AlertPriority.CRITICAL,
                    urgency_score=urgency,
                    due_date=p.due_date,
                    days_until_due=days,
                    amount=p.amount,
                    is_emi=p.is_emi,
                    alert_type="insufficient_balance",
                )
            )
            continue

        # CASE C: High EMI Due Very Soon (<= 5 days)
        if p.is_emi and days <= 5:
            urgency = 85 - days
            label = "High EMI" if is_high_val else "EMI"
            alerts.append(
                BillAlert(
                    title=f"⚠️ {label} Due in {days} Day{'s' if days != 1 else ''}",
                    message=(
                        f"{label} of ${p.amount:,.2f} for '{p.bill_name}' due in {days} day(s) "
                        f"on {p.due_date}. Please ensure sufficient balance is maintained."
                    ),
                    priority=AlertPriority.HIGH,
                    urgency_score=urgency,
                    due_date=p.due_date,
                    days_until_due=days,
                    amount=p.amount,
                    is_emi=True,
                    alert_type="high_emi_due",
                )
            )
            continue

        # CASE D: EMI Due Soon (6 to 10 days)
        if p.is_emi and days <= 10:
            urgency = 75 - (days - 5)
            alerts.append(
                BillAlert(
                    title=f"⚡ Upcoming EMI: {p.bill_name}",
                    message=(
                        f"Monthly EMI of ${p.amount:,.2f} for '{p.bill_name}' due in {days} days "
                        f"({p.due_date})."
                    ),
                    priority=AlertPriority.HIGH if is_high_val else AlertPriority.MEDIUM,
                    urgency_score=urgency,
                    due_date=p.due_date,
                    days_until_due=days,
                    amount=p.amount,
                    is_emi=True,
                    alert_type="emi_upcoming",
                )
            )
            continue

        # CASE E: Regular Bill Due Within 7 Days
        if days <= 7:
            urgency = 62 - days
            alerts.append(
                BillAlert(
                    title=f"📅 {p.category} Bill Due Soon",
                    message=(
                        f"{p.category} bill of ${p.amount:,.2f} for '{p.bill_name}' is due in "
                        f"{days} day(s) on {p.due_date}."
                    ),
                    priority=AlertPriority.MEDIUM,
                    urgency_score=urgency,
                    due_date=p.due_date,
                    days_until_due=days,
                    amount=p.amount,
                    is_emi=p.is_emi,
                    alert_type="bill_due_soon",
                )
            )
            continue

        # CASE F: EMI Due Later in the Month (11 to 30 days)
        if p.is_emi:
            urgency = max(35, 50 - (days // 2))
            alerts.append(
                BillAlert(
                    title=f"📌 Scheduled EMI: {p.bill_name}",
                    message=(
                        f"Scheduled EMI of ${p.amount:,.2f} for '{p.bill_name}' due on "
                        f"{p.due_date} ({days} days away)."
                    ),
                    priority=AlertPriority.MEDIUM,
                    urgency_score=urgency,
                    due_date=p.due_date,
                    days_until_due=days,
                    amount=p.amount,
                    is_emi=True,
                    alert_type="scheduled_emi",
                )
            )
            continue

        # CASE G: Regular Scheduled Bills (> 7 days away)
        urgency = max(15, 30 - (days // 3))
        alerts.append(
            BillAlert(
                title=f"ℹ️ Scheduled {p.category}: {p.bill_name}",
                message=(
                    f"Scheduled payment of ${p.amount:,.2f} for '{p.bill_name}' due on "
                    f"{p.due_date} ({days} days away)."
                ),
                priority=AlertPriority.LOW,
                urgency_score=urgency,
                due_date=p.due_date,
                days_until_due=days,
                amount=p.amount,
                is_emi=False,
                alert_type="scheduled_bill",
            )
        )

    # Sort alerts by urgency score descending, then by days_until_due ascending
    alerts.sort(
        key=lambda a: (
            -a.urgency_score,
            a.days_until_due if a.days_until_due is not None else 999,
            -(a.amount or 0.0),
        )
    )
    return alerts


# ── Object-Oriented Interface ────────────────────────────────────────────────

class BillTracker:
    """
    Stateful and cohesive tracker for recurring bills, EMI detection,
    outflow projections, and priority alerts.
    """

    def __init__(
        self,
        transactions: Optional[
            Union[Sequence[Transaction], pd.DataFrame, Sequence[Dict[str, Any]]]
        ] = None,
        as_of_date: Optional[date] = None,
        current_balance: Optional[float] = None,
        monthly_income: Optional[float] = None,
        amount_tolerance: float = 0.15,
        min_occurrences: int = 2,
    ):
        self.as_of_date = as_of_date
        self.current_balance = current_balance
        self.monthly_income = monthly_income
        self.amount_tolerance = amount_tolerance
        self.min_occurrences = min_occurrences

        self.recurring_bills: List[RecurringBill] = []
        self.upcoming_payments: List[UpcomingPayment] = []
        self.cash_outflow_projection: Optional[CashOutflowProjection] = None
        self.alerts: List[BillAlert] = []

        if transactions is not None:
            self.fit(transactions, as_of_date=as_of_date)

    def fit(
        self,
        transactions: Union[Sequence[Transaction], pd.DataFrame, Sequence[Dict[str, Any]]],
        as_of_date: Optional[date] = None,
    ) -> "BillTracker":
        """Process transactions and calculate recurring bills, projections, and alerts."""
        expenses, incomes = _standardize_transactions(transactions)

        if as_of_date is not None:
            self.as_of_date = as_of_date

        if self.as_of_date is None:
            all_dates = [x["date"] for x in expenses] + [x["date"] for x in incomes]
            self.as_of_date = max(all_dates) if all_dates else date.today()

        # Compute inferred monthly income if not provided
        if self.monthly_income is None and incomes:
            total_income = sum(x["amount"] for x in incomes)
            months_count = len({(x["date"].year, x["date"].month) for x in incomes}) or 1
            self.monthly_income = round(total_income / months_count, 2)

        self.recurring_bills = detect_recurring_bills(
            transactions,
            amount_tolerance=self.amount_tolerance,
            min_occurrences=self.min_occurrences,
            as_of_date=self.as_of_date,
        )

        self.upcoming_payments = calculate_upcoming_payments(
            self.recurring_bills, as_of_date=self.as_of_date, days_ahead=30
        )

        self.cash_outflow_projection = calculate_projected_cash_outflow(
            self.upcoming_payments, as_of_date=self.as_of_date, days_ahead=30
        )

        self.alerts = generate_priority_alerts(
            self.upcoming_payments,
            current_balance=self.current_balance,
            monthly_income=self.monthly_income,
        )
        return self

    def get_emis(self) -> List[RecurringBill]:
        """Return detected recurring bills that are classified as loan EMIs."""
        return [b for b in self.recurring_bills if b.is_emi]

    def get_alerts_by_urgency(self) -> List[BillAlert]:
        """Return alerts sorted by urgency (highest first)."""
        return self.alerts

    def set_balance(self, balance: float) -> List[BillAlert]:
        """Update current balance and re-generate alerts."""
        self.current_balance = balance
        self.alerts = generate_priority_alerts(
            self.upcoming_payments,
            current_balance=self.current_balance,
            monthly_income=self.monthly_income,
        )
        return self.alerts


# ── Simulation Data Generator ────────────────────────────────────────────────

def generate_simulated_transactions(
    as_of_date: Optional[date] = None,
) -> List[Transaction]:
    """
    Generate realistic 3-month simulated transactions including:
    - Monthly Home Loan EMI ($1,250.00 on 5th)
    - Monthly Car Loan EMI ($380.00 on 10th)
    - Monthly Rent ($1,400.00 on 1st)
    - Monthly Health Insurance ($210.00 on 15th)
    - Monthly Electricity Bill (~$110 on 18th)
    - Monthly Internet Bill ($60.00 on 12th)
    - Monthly Netflix Subscription ($15.99 on 8th)
    - Monthly Salary Credit ($5,000.00 on 1st)
    - Non-recurring everyday expenses with realistic date and amount variation
    """
    if as_of_date is None:
        as_of_date = date(2024, 4, 1)

    txs: List[Transaction] = []

    # Historical recurring payments for Jan, Feb, Mar 2024
    recurring_specs = [
        # (day_of_month, desc, base_amt, is_income, cat)
        (1, "Salary Credit", 5000.0, True, "Salary"),
        (1, "Apartment Rent", 1400.0, False, "Rent"),
        (5, "HDFC Home Loan EMI", 1250.0, False, "Loan / EMI"),
        (8, "Netflix Subscription", 15.99, False, "Subscription"),
        (10, "Car Loan EMI", 380.0, False, "Loan / EMI"),
        (12, "Internet Broadband Bill", 60.0, False, "Utility"),
        (15, "Health Insurance Premium", 210.0, False, "Insurance"),
    ]

    # Electricity bill with realistic slight variation
    electric_amounts = {1: 108.50, 2: 114.20, 3: 111.00}

    for month_num in (1, 2, 3):
        # Add recurring items
        for day, desc, amt, is_inc, cat in recurring_specs:
            txs.append(
                Transaction(
                    date=date(2024, month_num, day),
                    description=desc,
                    amount=amt if is_inc else -amt,
                    type="Income" if is_inc else "Expense",
                    category=cat,
                    source="csv",
                )
            )

        # Electric bill
        txs.append(
            Transaction(
                date=date(2024, month_num, 18),
                description="Electric Utility Bill",
                amount=-electric_amounts[month_num],
                type="Expense",
                category="Utility",
                source="csv",
            )
        )

    # Add everyday non-recurring expenses with variable dates and amounts (so they don't form artificial recurring patterns)
    variable_expenses = [
        (date(2024, 1, 3), "Grocery Store", -65.40),
        (date(2024, 1, 9), "Uber Ride", -14.20),
        (date(2024, 1, 21), "Italian Restaurant", -54.00),
        (date(2024, 1, 27), "Chevron Gas Station", -42.00),
        (date(2024, 2, 4), "Supermarket Grocery", -88.10),
        (date(2024, 2, 11), "Lyft Airport Ride", -32.50),
        (date(2024, 2, 19), "Cinema Popcorn Tickets", -28.00),
        (date(2024, 2, 26), "Shell Gas Station", -49.50),
        (date(2024, 3, 2), "Grocery Store", -72.30),
        (date(2024, 3, 16), "Sushi Dinner", -62.00),
        (date(2024, 3, 22), "Uber Ride", -18.75),
        (date(2024, 3, 29), "Exxon Fuel", -53.20),
    ]

    for d, desc, amt in variable_expenses:
        txs.append(
            Transaction(
                date=d,
                description=desc,
                amount=amt,
                type="Expense",
                category="Other",
                source="csv",
            )
        )

    txs.sort(key=lambda t: t.date)
    return txs
