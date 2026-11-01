"""
test_emergency_fund.py — Unit Tests for Chunk 6
Emergency Fund Planner & Financial Actions
Run with: python -m pytest tests/test_emergency_fund.py -v
"""

from datetime import date
import pandas as pd
import pytest

from src.ingestion.transaction import Transaction
from src.planning.emergency_fund import (
    SENIOR_MEDICAL_BUFFER_MONTHS,
    ActionStep,
    EmergencyCorpus,
    ExpenseProfile,
    FundGap,
    MilestoneReport,
    analyse_fund_gap,
    build_expense_profile,
    compute_emergency_corpus,
    generate_action_steps,
    generate_milestone_report,
    _months_to_reach,
    _target_date,
    _is_essential,
    _is_discretionary,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_transactions():
    """3 months of realistic transactions for integration tests."""
    return [
        # Income
        Transaction(date=date(2024, 1, 1), description="Salary", amount=5000.0,  type="Income",  category="Salary"),
        Transaction(date=date(2024, 2, 1), description="Salary", amount=5000.0,  type="Income",  category="Salary"),
        Transaction(date=date(2024, 3, 1), description="Salary", amount=5000.0,  type="Income",  category="Salary"),
        # Essential
        Transaction(date=date(2024, 1, 1), description="Apartment Rent",    amount=-1400.0, type="Expense", category="Rent"),
        Transaction(date=date(2024, 2, 1), description="Apartment Rent",    amount=-1400.0, type="Expense", category="Rent"),
        Transaction(date=date(2024, 3, 1), description="Apartment Rent",    amount=-1400.0, type="Expense", category="Rent"),
        Transaction(date=date(2024, 1, 5), description="Home Loan EMI",     amount=-1250.0, type="Expense", category="Loan / EMI"),
        Transaction(date=date(2024, 2, 5), description="Home Loan EMI",     amount=-1250.0, type="Expense", category="Loan / EMI"),
        Transaction(date=date(2024, 3, 5), description="Home Loan EMI",     amount=-1250.0, type="Expense", category="Loan / EMI"),
        Transaction(date=date(2024, 1, 18), description="Electric Bill",    amount=-110.0,  type="Expense", category="Utility"),
        Transaction(date=date(2024, 2, 18), description="Electric Bill",    amount=-110.0,  type="Expense", category="Utility"),
        Transaction(date=date(2024, 3, 18), description="Electric Bill",    amount=-110.0,  type="Expense", category="Utility"),
        # Discretionary
        Transaction(date=date(2024, 1, 10), description="Netflix",          amount=-15.99,  type="Expense", category="Subscription"),
        Transaction(date=date(2024, 2, 10), description="Netflix",          amount=-15.99,  type="Expense", category="Subscription"),
        Transaction(date=date(2024, 3, 10), description="Netflix",          amount=-15.99,  type="Expense", category="Subscription"),
        Transaction(date=date(2024, 1, 20), description="Amazon Shopping",  amount=-80.0,   type="Expense", category="Shopping"),
        Transaction(date=date(2024, 2, 20), description="Amazon Shopping",  amount=-90.0,   type="Expense", category="Shopping"),
    ]


# ── Helper function tests ─────────────────────────────────────────────────────

class TestHelpers:
    def test_months_to_reach_zero_gap(self):
        assert _months_to_reach(0, 500) == 0

    def test_months_to_reach_positive_gap(self):
        assert _months_to_reach(1000, 300) == 4   # ceil(1000/300)

    def test_months_to_reach_zero_contribution(self):
        assert _months_to_reach(1000, 0) is None

    def test_months_to_reach_exact(self):
        assert _months_to_reach(900, 300) == 3

    def test_target_date_already_reached(self):
        assert _target_date(0, date(2024, 1, 1)) == "Already reached"

    def test_target_date_none_contribution(self):
        assert _target_date(None, date(2024, 1, 1)) is None

    def test_target_date_future(self):
        result = _target_date(3, date(2024, 1, 1))
        assert result == "Apr 2024"

    def test_target_date_year_rollover(self):
        result = _target_date(4, date(2024, 11, 1))
        assert result == "Mar 2025"

    def test_is_essential_rent(self):
        assert _is_essential("Rent") is True

    def test_is_essential_emi(self):
        assert _is_essential("Loan / EMI") is True

    def test_is_essential_utility(self):
        assert _is_essential("Utility") is True

    def test_is_discretionary_entertainment(self):
        assert _is_discretionary("Entertainment") is True

    def test_is_discretionary_shopping(self):
        assert _is_discretionary("Shopping") is True

    def test_is_not_essential_shopping(self):
        assert _is_essential("Shopping") is False


# ── ExpenseProfile tests ──────────────────────────────────────────────────────

class TestBuildExpenseProfile:
    def test_profile_from_transactions(self):
        txs = _make_transactions()
        profile = build_expense_profile(txs)
        assert profile.months_analysed == 3
        assert profile.monthly_income == pytest.approx(5000.0, abs=1)
        # Essential: rent(1400) + emi(1250) + electric(110) = 2760/month
        assert profile.monthly_essential == pytest.approx(2760.0, abs=1)
        # Discretionary: netflix(15.99) + shopping(~85/month avg)
        assert profile.monthly_discretionary > 0

    def test_profile_from_dataframe(self):
        df = pd.DataFrame([
            {"Date": "2024-01-01", "Description": "Salary",       "Amount":  5000.0, "Type": "Income",  "Category": "Salary"},
            {"Date": "2024-01-05", "Description": "Rent Payment",  "Amount": -1200.0, "Type": "Expense", "Category": "Rent"},
            {"Date": "2024-01-10", "Description": "Grocery Store", "Amount":  -200.0, "Type": "Expense", "Category": "Grocery"},
        ])
        profile = build_expense_profile(df)
        assert profile.monthly_income == pytest.approx(5000.0, abs=1)
        assert profile.monthly_essential > 0

    def test_profile_empty_returns_zeros(self):
        profile = build_expense_profile([])
        assert profile.monthly_essential == 0
        assert profile.monthly_total == 0

    def test_profile_flags_subscriptions(self):
        txs = _make_transactions()
        profile = build_expense_profile(txs)
        assert len(profile.flagged_subscriptions) >= 1
        names = [s["name"] for s in profile.flagged_subscriptions]
        assert any("Netflix" in n for n in names)

    def test_profile_category_breakdown_populated(self):
        txs = _make_transactions()
        profile = build_expense_profile(txs)
        assert "Rent" in profile.category_breakdown
        assert "Loan / EMI" in profile.category_breakdown


# ── EmergencyCorpus tests ─────────────────────────────────────────────────────

class TestComputeEmergencyCorpus:
    def _profile(self, essential=2000.0, total=3000.0, income=5000.0):
        return ExpenseProfile(
            monthly_essential=essential,
            monthly_discretionary=total - essential,
            monthly_total=total,
            monthly_income=income,
            months_analysed=3,
        )

    def test_standard_corpus_targets(self):
        corpus = compute_emergency_corpus(self._profile())
        assert corpus.target_3m == pytest.approx(6000.0)
        assert corpus.target_6m == pytest.approx(12000.0)
        assert corpus.recommended_target == pytest.approx(12000.0)
        assert corpus.is_senior is False

    def test_senior_corpus_adds_buffer(self):
        corpus = compute_emergency_corpus(self._profile(), is_senior=True)
        expected = 2000.0 * (6 + SENIOR_MEDICAL_BUFFER_MONTHS)
        assert corpus.target_senior == pytest.approx(expected)
        assert corpus.recommended_target == pytest.approx(expected)
        assert corpus.is_senior is True
        assert corpus.coverage_months == 6 + SENIOR_MEDICAL_BUFFER_MONTHS

    def test_custom_essential_overrides_profile(self):
        corpus = compute_emergency_corpus(self._profile(), custom_monthly_essential=3000.0)
        assert corpus.target_6m == pytest.approx(18000.0)

    def test_zero_essential_falls_back_to_50pct_total(self):
        profile = self._profile(essential=0.0, total=4000.0)
        corpus  = compute_emergency_corpus(profile)
        # fallback: 50% of 4000 = 2000 essential → 6m = 12000
        assert corpus.target_6m == pytest.approx(12000.0)


# ── FundGap tests ─────────────────────────────────────────────────────────────

class TestAnalyseFundGap:
    def _corpus(self, target=12000.0):
        return EmergencyCorpus(
            target_3m=6000.0, target_6m=target, target_senior=16000.0,
            recommended_target=target, coverage_months=6.0, is_senior=False,
        )

    def test_gap_with_shortfall(self):
        gap = analyse_fund_gap(self._corpus(12000), current_savings=4000)
        assert gap.gap == pytest.approx(8000.0)
        assert gap.pct_funded == pytest.approx(33.3, abs=0.2)
        assert gap.is_funded is False

    def test_gap_fully_funded(self):
        gap = analyse_fund_gap(self._corpus(12000), current_savings=15000)
        assert gap.is_funded is True
        assert gap.pct_funded == 100.0
        assert gap.gap < 0   # surplus

    def test_gap_exactly_at_target(self):
        gap = analyse_fund_gap(self._corpus(12000), current_savings=12000)
        assert gap.is_funded is True
        assert gap.gap == pytest.approx(0.0)


# ── ActionStep tests ──────────────────────────────────────────────────────────

class TestGenerateActionSteps:
    def _gap(self, current=4000, target=12000):
        return FundGap(
            current_savings=current, target=target,
            gap=target - current,
            pct_funded=round(current / target * 100, 1),
            is_funded=current >= target,
        )

    def _profile(self):
        p = ExpenseProfile(
            monthly_essential=2760.0, monthly_discretionary=200.0,
            monthly_total=2960.0, monthly_income=5000.0, months_analysed=3,
        )
        p.flagged_subscriptions = [{"name": "Netflix", "amount": 15.99}]
        return p

    def test_returns_list_of_action_steps(self):
        steps = generate_action_steps(self._profile(), self._gap(), 500.0)
        assert len(steps) >= 2
        assert all(isinstance(s, ActionStep) for s in steps)

    def test_first_step_is_monthly_allocation(self):
        steps = generate_action_steps(self._profile(), self._gap(), 500.0)
        assert steps[0].priority == 1
        assert "500" in steps[0].detail

    def test_subscription_step_included(self):
        steps = generate_action_steps(self._profile(), self._gap(), 500.0)
        sub_steps = [s for s in steps if "Subscription" in s.action]
        assert len(sub_steps) == 1
        assert "Netflix" in sub_steps[0].detail

    def test_funded_returns_invest_surplus_step(self):
        funded_gap = self._gap(current=15000, target=12000)
        steps = generate_action_steps(self._profile(), funded_gap, 500.0)
        assert len(steps) == 1
        assert "Surplus" in steps[0].action

    def test_step_detail_contains_currency_symbol(self):
        steps = generate_action_steps(self._profile(), self._gap(), 3000.0, currency="₹")
        assert any("₹" in s.detail for s in steps)


# ── MilestoneReport integration tests ────────────────────────────────────────

class TestGenerateMilestoneReport:
    def test_report_structure(self):
        txs    = _make_transactions()
        report = generate_milestone_report(txs, current_savings=5000, planned_monthly_contribution=500)
        assert isinstance(report, MilestoneReport)
        assert report.profile.monthly_income > 0
        assert report.corpus.target_3m > 0
        assert report.corpus.target_6m > report.corpus.target_3m
        assert len(report.milestones) == 2       # 3m and 6m
        assert len(report.action_steps) >= 1
        assert len(report.summary_lines) >= 3

    def test_senior_report_has_3_milestones(self):
        txs    = _make_transactions()
        report = generate_milestone_report(txs, current_savings=5000,
                                           planned_monthly_contribution=500, is_senior=True)
        assert len(report.milestones) == 3
        labels = [m["label"] for m in report.milestones]
        assert any("Senior" in l for l in labels)

    def test_report_months_to_target_calculated(self):
        txs    = _make_transactions()
        report = generate_milestone_report(txs, current_savings=0,
                                           planned_monthly_contribution=1000)
        assert report.months_to_3m_target is not None
        assert report.months_to_6m_target >= report.months_to_3m_target

    def test_report_fully_funded_scenario(self):
        txs    = _make_transactions()
        report = generate_milestone_report(txs, current_savings=999999,
                                           planned_monthly_contribution=500)
        assert report.gap.is_funded is True
        assert report.months_to_recommended_target == 0

    def test_report_summary_contains_shortfall(self):
        txs    = _make_transactions()
        report = generate_milestone_report(txs, current_savings=1000,
                                           planned_monthly_contribution=500)
        assert any("Shortfall" in line for line in report.summary_lines)

    def test_report_with_custom_essential(self):
        txs    = _make_transactions()
        report = generate_milestone_report(txs, current_savings=5000,
                                           planned_monthly_contribution=500,
                                           custom_monthly_essential=3000.0)
        assert report.corpus.target_6m == pytest.approx(18000.0)

    def test_report_from_dataframe(self):
        df = pd.DataFrame([
            {"Date": "2024-01-01", "Description": "Salary",      "Amount":  5000.0, "Type": "Income",  "Category": "Salary"},
            {"Date": "2024-01-05", "Description": "Rent",         "Amount": -1500.0, "Type": "Expense", "Category": "Rent"},
            {"Date": "2024-02-01", "Description": "Salary",      "Amount":  5000.0, "Type": "Income",  "Category": "Salary"},
            {"Date": "2024-02-05", "Description": "Rent",         "Amount": -1500.0, "Type": "Expense", "Category": "Rent"},
        ])
        report = generate_milestone_report(df, current_savings=3000, planned_monthly_contribution=500)
        assert report.corpus.target_3m == pytest.approx(4500.0)
        assert report.corpus.target_6m == pytest.approx(9000.0)
