"""
test_bill_tracker.py — Unit Tests for Chunk 4 (Recurring Bills, EMI Detector & Alert System)
"""

from datetime import date, timedelta
import pandas as pd
import pytest

from src.ingestion.transaction import Transaction
from src.planning.bill_tracker import (
    AlertPriority,
    BillAlert,
    BillCategory,
    BillTracker,
    CashOutflowProjection,
    RecurringBill,
    UpcomingPayment,
    _add_months,
    _clean_description,
    _infer_category_and_emi,
    calculate_projected_cash_outflow,
    calculate_upcoming_payments,
    detect_recurring_bills,
    generate_priority_alerts,
    generate_simulated_transactions,
)


# ── Test Normalization & Helper Functions ────────────────────────────────────

class TestHelpers:
    def test_clean_description_removes_ref_and_dates(self):
        desc = "HDFC Home Loan EMI Ref #TX987654 2024-01-05"
        cleaned = _clean_description(desc)
        assert "987654" not in cleaned
        assert "2024" not in cleaned
        assert "hdfc home loan emi" in cleaned

    def test_clean_description_removes_months(self):
        desc = "Car Loan EMI - Auto Debit January"
        cleaned = _clean_description(desc)
        assert "january" not in cleaned
        assert "car loan emi" in cleaned

    def test_add_months_standard(self):
        assert _add_months(date(2024, 1, 15), 1) == date(2024, 2, 15)
        assert _add_months(date(2024, 1, 15), 3) == date(2024, 4, 15)

    def test_add_months_month_end_leap_year(self):
        # 2024 is a leap year
        assert _add_months(date(2024, 1, 31), 1) == date(2024, 2, 29)
        # 2023 is not a leap year
        assert _add_months(date(2023, 1, 31), 1) == date(2023, 2, 28)

    def test_add_months_year_rollover(self):
        assert _add_months(date(2024, 11, 20), 2) == date(2025, 1, 20)

    def test_infer_category_and_emi_loan(self):
        cat, is_emi = _infer_category_and_emi("HDFC Home Loan EMI")
        assert cat == BillCategory.EMI_LOAN.value
        assert is_emi is True

    def test_infer_category_and_emi_rent(self):
        cat, is_emi = _infer_category_and_emi("Apartment Rent Payment")
        assert cat == BillCategory.RENT.value
        assert is_emi is False

    def test_infer_category_and_emi_insurance_not_emi(self):
        # Ensure 'premium' doesn't accidentally trigger 'emi' keyword
        cat, is_emi = _infer_category_and_emi("Health Insurance Premium")
        assert cat == BillCategory.INSURANCE.value
        assert is_emi is False

    def test_infer_category_and_emi_utility(self):
        cat, is_emi = _infer_category_and_emi("Electric Power Utility Bill")
        assert cat == BillCategory.UTILITY.value
        assert is_emi is False

    def test_infer_category_and_emi_subscription(self):
        cat, is_emi = _infer_category_and_emi("Netflix Subscription")
        assert cat == BillCategory.SUBSCRIPTION.value
        assert is_emi is False


# ── Test Recurring Bill & EMI Detection ───────────────────────────────────────

class TestRecurringBillDetection:
    def test_detect_monthly_loan_emi(self):
        txs = [
            Transaction(date=date(2024, 1, 5), description="HDFC Home Loan EMI", amount=-1250.0, type="Expense"),
            Transaction(date=date(2024, 2, 5), description="HDFC Home Loan EMI", amount=-1250.0, type="Expense"),
            Transaction(date=date(2024, 3, 5), description="HDFC Home Loan EMI", amount=-1250.0, type="Expense"),
        ]
        bills = detect_recurring_bills(txs, as_of_date=date(2024, 4, 1))
        assert len(bills) == 1
        b = bills[0]
        assert b.is_emi is True
        assert b.category == BillCategory.EMI_LOAN.value
        assert b.expected_amount == 1250.0
        assert b.frequency == "monthly"
        assert b.payment_count == 3
        assert b.next_due_date == date(2024, 4, 5)

    def test_detect_multiple_emis_and_rent(self):
        txs = [
            # Home loan
            Transaction(date=date(2024, 1, 5), description="Home Loan EMI", amount=-1200.0, type="Expense"),
            Transaction(date=date(2024, 2, 5), description="Home Loan EMI", amount=-1200.0, type="Expense"),
            # Car loan
            Transaction(date=date(2024, 1, 10), description="Car Loan EMI", amount=-350.0, type="Expense"),
            Transaction(date=date(2024, 2, 10), description="Car Loan EMI", amount=-350.0, type="Expense"),
            # Rent
            Transaction(date=date(2024, 1, 1), description="Apartment Rent", amount=-1500.0, type="Expense"),
            Transaction(date=date(2024, 2, 1), description="Apartment Rent", amount=-1500.0, type="Expense"),
        ]
        bills = detect_recurring_bills(txs, as_of_date=date(2024, 3, 1))
        assert len(bills) == 3
        emis = [b for b in bills if b.is_emi]
        assert len(emis) == 2
        emi_names = {b.name for b in emis}
        assert "Home Loan EMI" in emi_names
        assert "Car Loan EMI" in emi_names

    def test_detect_utility_with_minor_amount_variation(self):
        txs = [
            Transaction(date=date(2024, 1, 18), description="Electric Utility Bill", amount=-105.0, type="Expense"),
            Transaction(date=date(2024, 2, 18), description="Electric Utility Bill", amount=-115.0, type="Expense"),
            Transaction(date=date(2024, 3, 18), description="Electric Utility Bill", amount=-110.0, type="Expense"),
        ]
        bills = detect_recurring_bills(txs, amount_tolerance=0.15)
        assert len(bills) == 1
        b = bills[0]
        assert b.category == BillCategory.UTILITY.value
        assert b.is_emi is False
        assert 109.0 <= b.expected_amount <= 111.0

    def test_ignore_one_off_expenses(self):
        txs = [
            Transaction(date=date(2024, 1, 5), description="HDFC Home Loan EMI", amount=-1250.0, type="Expense"),
            Transaction(date=date(2024, 2, 5), description="HDFC Home Loan EMI", amount=-1250.0, type="Expense"),
            Transaction(date=date(2024, 1, 12), description="Concert Tickets", amount=-150.0, type="Expense"),
            Transaction(date=date(2024, 2, 20), description="New Shoes", amount=-90.0, type="Expense"),
        ]
        bills = detect_recurring_bills(txs, min_occurrences=2)
        assert len(bills) == 1
        assert bills[0].name == "HDFC Home Loan EMI"

    def test_income_is_not_treated_as_recurring_expense_bill(self):
        txs = [
            Transaction(date=date(2024, 1, 1), description="Salary Credit", amount=5000.0, type="Income"),
            Transaction(date=date(2024, 2, 1), description="Salary Credit", amount=5000.0, type="Income"),
            Transaction(date=date(2024, 3, 1), description="Salary Credit", amount=5000.0, type="Income"),
            Transaction(date=date(2024, 1, 5), description="Car Loan EMI", amount=-300.0, type="Expense"),
            Transaction(date=date(2024, 2, 5), description="Car Loan EMI", amount=-300.0, type="Expense"),
        ]
        bills = detect_recurring_bills(txs)
        assert len(bills) == 1
        assert bills[0].name == "Car Loan EMI"

    def test_empty_transactions_returns_empty_list(self):
        assert detect_recurring_bills([]) == []
        assert detect_recurring_bills(pd.DataFrame()) == []

    def test_dataframe_input_parsing(self):
        df = pd.DataFrame([
            {"Date": "2024-01-10", "Description": "Netflix Subscription", "Amount": -15.99, "Type": "Expense"},
            {"Date": "2024-02-10", "Description": "Netflix Subscription", "Amount": -15.99, "Type": "Expense"},
            {"Date": "2024-03-10", "Description": "Netflix Subscription", "Amount": -15.99, "Type": "Expense"},
        ])
        bills = detect_recurring_bills(df)
        assert len(bills) == 1
        assert bills[0].name == "Netflix Subscription"
        assert bills[0].category == BillCategory.SUBSCRIPTION.value


# ── Test Upcoming Payments & 30-Day Projections ───────────────────────────────

class TestCashOutflowProjection:
    def test_calculate_upcoming_payments_within_30_days(self):
        bill = RecurringBill(
            name="HDFC Home Loan EMI",
            category=BillCategory.EMI_LOAN.value,
            expected_amount=1250.0,
            frequency="monthly",
            interval_days=30.0,
            last_payment_date=date(2024, 3, 5),
            next_due_date=date(2024, 4, 5),
            payment_count=3,
            is_emi=True,
        )
        as_of = date(2024, 4, 1)
        payments = calculate_upcoming_payments([bill], as_of_date=as_of, days_ahead=30)
        assert len(payments) == 1
        assert payments[0].due_date == date(2024, 4, 5)
        assert payments[0].days_until_due == 4
        assert payments[0].amount == 1250.0
        assert payments[0].is_emi is True

    def test_calculate_projected_cash_outflow_breakdown(self):
        b1 = RecurringBill(
            name="Home Loan EMI",
            category=BillCategory.EMI_LOAN.value,
            expected_amount=1000.0,
            frequency="monthly",
            interval_days=30.0,
            last_payment_date=date(2024, 3, 5),
            next_due_date=date(2024, 4, 5),
            payment_count=3,
            is_emi=True,
        )
        b2 = RecurringBill(
            name="Electric Bill",
            category=BillCategory.UTILITY.value,
            expected_amount=100.0,
            frequency="monthly",
            interval_days=30.0,
            last_payment_date=date(2024, 3, 10),
            next_due_date=date(2024, 4, 10),
            payment_count=3,
            is_emi=False,
        )
        as_of = date(2024, 4, 1)
        proj = calculate_projected_cash_outflow([b1, b2], as_of_date=as_of, days_ahead=30)
        assert proj.total_projected_outflow == 1100.0
        assert proj.total_emi_outflow == 1000.0
        assert proj.total_non_emi_outflow == 100.0
        assert proj.total_bills_count == 2
        assert "2024-04-05" in proj.daily_outflows
        assert "2024-04-10" in proj.daily_outflows


# ── Test Priority Alerts & Urgency Sorting ────────────────────────────────────

class TestPriorityAlerts:
    def test_alert_high_emi_due_in_4_days_insufficient_balance(self):
        """
        Verify: 'High EMI due in 4 days. Projected balance may be insufficient'
        """
        payment = UpcomingPayment(
            bill_name="HDFC Home Loan EMI",
            category=BillCategory.EMI_LOAN.value,
            amount=1250.0,
            due_date=date(2024, 4, 5),
            days_until_due=4,
            is_emi=True,
            urgency_status="Due Soon",
        )
        # Current balance is only $500, which is insufficient for $1,250 EMI
        alerts = generate_priority_alerts([payment], current_balance=500.0)

        # There should be an insufficient balance alert
        insufficient_alerts = [a for a in alerts if a.alert_type == "insufficient_balance"]
        assert len(insufficient_alerts) == 1
        alert = insufficient_alerts[0]
        assert alert.priority == AlertPriority.CRITICAL
        assert "High EMI of $1,250.00" in alert.message
        assert "due in 4 day(s)" in alert.message
        assert "may be insufficient" in alert.message

    def test_alert_high_emi_due_soon_sufficient_balance(self):
        payment = UpcomingPayment(
            bill_name="HDFC Home Loan EMI",
            category=BillCategory.EMI_LOAN.value,
            amount=1250.0,
            due_date=date(2024, 4, 5),
            days_until_due=4,
            is_emi=True,
            urgency_status="Due Soon",
        )
        # Ample balance: $10,000
        alerts = generate_priority_alerts([payment], current_balance=10000.0)
        assert len(alerts) >= 1
        emi_alert = [a for a in alerts if a.alert_type == "high_emi_due"][0]
        assert emi_alert.priority == AlertPriority.HIGH
        assert emi_alert.days_until_due == 4
        assert "due in 4 day(s)" in emi_alert.message

    def test_alerts_sorted_by_urgency_descending(self):
        payments = [
            UpcomingPayment(
                bill_name="Phone Bill",
                category="Utility",
                amount=50.0,
                due_date=date(2024, 4, 25),
                days_until_due=24,
                is_emi=False,
                urgency_status="Upcoming",
            ),
            UpcomingPayment(
                bill_name="Internet Bill",
                category="Utility",
                amount=60.0,
                due_date=date(2024, 4, 4),
                days_until_due=3,
                is_emi=False,
                urgency_status="Due Soon",
            ),
            UpcomingPayment(
                bill_name="Car Loan EMI",
                category="Loan / EMI",
                amount=400.0,
                due_date=date(2024, 4, 5),
                days_until_due=4,
                is_emi=True,
                urgency_status="Due Soon",
            ),
        ]
        alerts = generate_priority_alerts(payments, current_balance=100.0)
        # Check that alerts are sorted with highest urgency score first
        scores = [a.urgency_score for a in alerts]
        assert scores == sorted(scores, reverse=True)
        # Top alert should be CRITICAL (insufficient balance for upcoming items)
        assert alerts[0].priority == AlertPriority.CRITICAL

    def test_overdue_payment_alert(self):
        payment = UpcomingPayment(
            bill_name="Apartment Rent",
            category="Rent",
            amount=1400.0,
            due_date=date(2024, 3, 28),
            days_until_due=-3,
            is_emi=False,
            urgency_status="Overdue",
        )
        alerts = generate_priority_alerts([payment], current_balance=2000.0)
        overdue_alerts = [a for a in alerts if a.alert_type == "overdue"]
        assert len(overdue_alerts) == 1
        assert overdue_alerts[0].priority == AlertPriority.CRITICAL
        assert overdue_alerts[0].urgency_score >= 95


# ── Test BillTracker Integration & Verification ───────────────────────────────

class TestBillTrackerIntegration:
    def test_detect_simulated_monthly_emis_and_sorted_alerts(self):
        """
        Verification: Detect simulated monthly EMIs and produce an alert list sorted by urgency.
        """
        txs = generate_simulated_transactions()
        tracker = BillTracker(txs, as_of_date=date(2024, 4, 1), current_balance=800.0)

        # 1. Verify detected recurring bills
        assert len(tracker.recurring_bills) >= 5

        # 2. Verify detected monthly EMIs
        emis = tracker.get_emis()
        assert len(emis) >= 2
        emi_names = [e.name for e in emis]
        assert "HDFC Home Loan EMI" in emi_names
        assert "Car Loan EMI" in emi_names
        for e in emis:
            assert e.is_emi is True
            assert e.frequency == "monthly"

        # 3. Verify 30-day projection
        proj = tracker.cash_outflow_projection
        assert proj is not None
        assert proj.total_projected_outflow > 3000.0
        assert proj.total_emi_outflow > 1000.0
        assert len(proj.upcoming_payments) > 0

        # 4. Verify priority alerts sorted by urgency
        alerts = tracker.get_alerts_by_urgency()
        assert len(alerts) > 0

        # Verify sorted order
        for i in range(len(alerts) - 1):
            assert alerts[i].urgency_score >= alerts[i + 1].urgency_score

        # Verify specific critical high EMI alert when balance is insufficient ($800 < $1400 rent + $1250 EMI)
        home_emi_alerts = [
            a for a in alerts if "HDFC Home Loan EMI" in a.message and a.priority == AlertPriority.CRITICAL
        ]
        assert len(home_emi_alerts) == 1
        assert "due in 4 day(s)" in home_emi_alerts[0].message
        assert "insufficient" in home_emi_alerts[0].message.lower()

    def test_set_balance_dynamically_updates_alerts(self):
        txs = generate_simulated_transactions()
        tracker = BillTracker(txs, as_of_date=date(2024, 4, 1), current_balance=10000.0)

        # With $10,000 balance, no insufficient balance alert
        critical_alerts = [a for a in tracker.alerts if a.priority == AlertPriority.CRITICAL]
        assert len(critical_alerts) == 0

        # Dynamically lower balance to $200
        new_alerts = tracker.set_balance(200.0)
        critical_alerts_after = [a for a in new_alerts if a.priority == AlertPriority.CRITICAL]
        assert len(critical_alerts_after) > 0
