"""
test_ai_assistant.py — Unit tests for AI assistant modules.
Tests: financial_context, prompts, financial_assistant.
"""

import pandas as pd
import pytest

from src.assistant.prompts import detect_intent, FALLBACK_RESPONSE, NO_DATA_RESPONSE
from src.assistant.financial_context import build_financial_context, FinancialContext
from src.assistant.financial_assistant import generate_response, SUGGESTED_QUESTIONS, WELCOME_MESSAGE


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_df():
    """Minimal transactions DataFrame for testing."""
    data = {
        "Date": pd.to_datetime([
            "2024-01-05", "2024-01-10", "2024-01-15", "2024-01-20",
            "2024-02-05", "2024-02-10", "2024-02-15", "2024-02-20",
        ]),
        "Description": [
            "Salary Credit", "Grocery Store", "Netflix Subscription", "Uber Ride",
            "Salary Credit", "Restaurant Dinner", "Electric Bill", "Amazon Shopping",
        ],
        "Amount": [50000, -3000, -500, -400, 50000, -2500, -1200, -4000],
        "Type":   ["Income", "Expense", "Expense", "Expense",
                   "Income", "Expense", "Expense", "Expense"],
        "Category": ["Other", "Food", "Bills", "Transport",
                     "Other", "Food", "Bills", "Shopping"],
        "Month": ["Jan 2024", "Jan 2024", "Jan 2024", "Jan 2024",
                  "Feb 2024", "Feb 2024", "Feb 2024", "Feb 2024"],
    }
    return pd.DataFrame(data)


# ── prompts.py tests ──────────────────────────────────────────────────────────

class TestDetectIntent:
    def test_reduce_expenses(self):
        assert detect_intent("How can I reduce my expenses?") == "reduce_expenses"

    def test_save_money(self):
        assert detect_intent("How can I save more money?") == "reduce_expenses"

    def test_spending_breakdown(self):
        assert detect_intent("Where am I spending the most?") == "spending_breakdown"

    def test_health_score(self):
        assert detect_intent("What is my financial health score?") == "health_score"

    def test_emergency_fund(self):
        assert detect_intent("How much emergency fund do I need?") == "emergency_fund"

    def test_emi_bills(self):
        assert detect_intent("Which EMI payments are upcoming?") == "emi_bills"

    def test_income(self):
        assert detect_intent("What is my total income?") == "income"

    def test_balance(self):
        assert detect_intent("What is my remaining balance?") == "balance"

    def test_budget(self):
        assert detect_intent("Am I over budget?") == "budget"

    def test_fallback(self):
        assert detect_intent("Tell me a joke") == "fallback"

    def test_case_insensitive(self):
        assert detect_intent("WHAT IS MY HEALTH SCORE") == "health_score"


# ── financial_context.py tests ────────────────────────────────────────────────

class TestBuildFinancialContext:
    def test_none_df_returns_no_data(self):
        ctx = build_financial_context(None)
        assert ctx.has_data is False

    def test_empty_df_returns_no_data(self):
        ctx = build_financial_context(pd.DataFrame())
        assert ctx.has_data is False

    def test_has_data_true(self, sample_df):
        ctx = build_financial_context(sample_df)
        assert ctx.has_data is True

    def test_income_calculated(self, sample_df):
        ctx = build_financial_context(sample_df)
        assert ctx.total_income == pytest.approx(100000.0)

    def test_expense_calculated(self, sample_df):
        ctx = build_financial_context(sample_df)
        assert ctx.total_expense == pytest.approx(11600.0)

    def test_balance_calculated(self, sample_df):
        ctx = build_financial_context(sample_df)
        assert ctx.balance == pytest.approx(88400.0)

    def test_savings_rate_positive(self, sample_df):
        ctx = build_financial_context(sample_df)
        assert ctx.savings_rate > 0

    def test_health_score_range(self, sample_df):
        ctx = build_financial_context(sample_df)
        assert 0 <= ctx.health_score <= 100

    def test_top_category_set(self, sample_df):
        ctx = build_financial_context(sample_df)
        assert ctx.top_category is not None

    def test_category_breakdown_populated(self, sample_df):
        ctx = build_financial_context(sample_df)
        assert len(ctx.category_breakdown) > 0

    def test_months_analysed(self, sample_df):
        ctx = build_financial_context(sample_df)
        assert ctx.months_analysed == 2

    def test_monthly_income(self, sample_df):
        ctx = build_financial_context(sample_df)
        assert ctx.monthly_income == pytest.approx(50000.0)

    def test_emergency_targets_positive(self, sample_df):
        ctx = build_financial_context(sample_df)
        assert ctx.target_3m > 0
        assert ctx.target_6m > ctx.target_3m
        assert ctx.target_senior >= ctx.target_6m

    def test_insights_generated(self, sample_df):
        ctx = build_financial_context(sample_df)
        assert len(ctx.insights) > 0

    def test_action_steps_generated(self, sample_df):
        ctx = build_financial_context(sample_df)
        assert len(ctx.action_steps) > 0


# ── financial_assistant.py tests ─────────────────────────────────────────────

class TestGenerateResponse:
    def test_no_data_returns_upload_message(self):
        resp = generate_response("How can I save?", None)
        assert "upload" in resp.lower() or "data" in resp.lower()

    def test_empty_df_returns_upload_message(self):
        resp = generate_response("Where am I spending?", pd.DataFrame())
        assert "upload" in resp.lower() or "data" in resp.lower()

    def test_reduce_expenses_response(self, sample_df):
        resp = generate_response("How can I reduce my expenses?", sample_df)
        assert "₹" in resp
        assert len(resp) > 50

    def test_spending_breakdown_response(self, sample_df):
        resp = generate_response("Where am I spending the most?", sample_df)
        assert "₹" in resp

    def test_health_score_response(self, sample_df):
        resp = generate_response("What is my financial health score?", sample_df)
        assert "/100" in resp

    def test_emergency_fund_response(self, sample_df):
        resp = generate_response("How much emergency fund do I need?", sample_df)
        assert "₹" in resp
        assert "3" in resp or "6" in resp

    def test_emi_response(self, sample_df):
        resp = generate_response("Which EMI payments are upcoming?", sample_df)
        assert len(resp) > 20

    def test_income_response(self, sample_df):
        resp = generate_response("What is my total income?", sample_df)
        assert "₹" in resp

    def test_balance_response(self, sample_df):
        resp = generate_response("What is my remaining balance?", sample_df)
        assert "₹" in resp

    def test_budget_response(self, sample_df):
        resp = generate_response("Am I over budget?", sample_df)
        assert "budget" in resp.lower() or "₹" in resp

    def test_fallback_response(self, sample_df):
        resp = generate_response("Tell me a joke", sample_df)
        assert "?" in resp or "help" in resp.lower()

    def test_prebuilt_context_used(self, sample_df):
        from src.assistant.financial_context import build_financial_context
        ctx = build_financial_context(sample_df)
        resp = generate_response("What is my health score?", sample_df, ctx=ctx)
        assert "/100" in resp

    def test_no_hardcoded_figures(self, sample_df):
        """Response figures must come from data, not be hardcoded."""
        ctx = build_financial_context(sample_df)
        resp = generate_response("What is my financial health score?", sample_df, ctx=ctx)
        assert str(ctx.health_score) in resp

    def test_suggested_questions_count(self):
        assert len(SUGGESTED_QUESTIONS) == 5

    def test_welcome_message_not_empty(self):
        assert len(WELCOME_MESSAGE) > 20
