import pytest
from datetime import date
from src.ingestion.transaction import Transaction
from src.intelligence.risk_engine import (
    compute_risk_score,
    _emi_burden_score,
    _volatility_score,
    _liquidity_score,
    _savings_score,
    RiskResult,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_txn(desc, amount, txn_type, txn_date, balance=None):
    t = Transaction(date=txn_date, description=desc, amount=amount, type=txn_type)
    if balance is not None:
        t = t.model_copy(update={"balance": balance})
    return t


def healthy_transactions():
    """Low expenses, good income, stable spending."""
    return [
        make_txn("Salary",  50000, "Income",  date(2024, 1, 1), balance=50000),
        make_txn("Grocery",  -3000, "Expense", date(2024, 1, 5), balance=47000),
        make_txn("Utilities",-1500, "Expense", date(2024, 1, 10), balance=45500),
        make_txn("Transport",-1000, "Expense", date(2024, 1, 15), balance=44500),
        make_txn("Salary",  50000, "Income",  date(2024, 2, 1), balance=94500),
        make_txn("Grocery",  -3200, "Expense", date(2024, 2, 5), balance=91300),
        make_txn("Utilities",-1500, "Expense", date(2024, 2, 10), balance=89800),
        make_txn("Transport",-1100, "Expense", date(2024, 2, 15), balance=88700),
    ]


def high_debt_transactions():
    """High EMI, low savings, low balance."""
    return [
        make_txn("Salary",  30000, "Income",  date(2024, 1, 1), balance=5000),
        make_txn("EMI Loan",-15000, "Expense", date(2024, 1, 3), balance=-10000),
        make_txn("Grocery",  -5000, "Expense", date(2024, 1, 10), balance=-15000),
        make_txn("Salary",  30000, "Income",  date(2024, 2, 1), balance=15000),
        make_txn("EMI Loan",-15000, "Expense", date(2024, 2, 3), balance=0),
        make_txn("Grocery",  -8000, "Expense", date(2024, 2, 10), balance=-8000),
    ]


# ── Factor unit tests ─────────────────────────────────────────────────────────

class TestEMIBurdenScore:
    def test_healthy_emi(self):
        pts, ratio, msg = _emi_burden_score(5000, 50000)
        assert pts == 0 and ratio == pytest.approx(0.10)

    def test_moderate_emi(self):
        pts, ratio, msg = _emi_burden_score(18000, 50000)  # 36% → moderate
        assert pts == 15

    def test_high_emi(self):
        pts, ratio, msg = _emi_burden_score(25000, 50000)  # 50% → high burden
        assert pts == 25

    def test_critical_emi(self):
        pts, ratio, msg = _emi_burden_score(40000, 50000)
        assert pts == 35

    def test_zero_income_returns_max(self):
        pts, ratio, msg = _emi_burden_score(5000, 0)
        assert pts == 35

    def test_explanation_contains_percentage(self):
        _, _, msg = _emi_burden_score(18000, 50000)
        assert "36.0%" in msg


class TestVolatilityScore:
    def test_stable_spending(self):
        pts, cv, _ = _volatility_score([5000, 5100, 4950, 5050])
        assert pts == 0

    def test_moderate_volatility(self):
        pts, cv, _ = _volatility_score([3000, 4500, 3200, 5000])
        assert pts == 10

    def test_high_volatility(self):
        pts, cv, _ = _volatility_score([1000, 8000, 1500, 9000])
        assert pts >= 18

    def test_single_month_returns_zero(self):
        pts, cv, _ = _volatility_score([5000])
        assert pts == 0

    def test_empty_returns_zero(self):
        pts, cv, _ = _volatility_score([])
        assert pts == 0


class TestLiquidityScore:
    def test_excellent_buffer(self):
        pts, days, _ = _liquidity_score(30000, 5000)
        assert pts == 0 and days == pytest.approx(180.0)

    def test_moderate_buffer(self):
        # 75 days
        pts, days, _ = _liquidity_score(12500, 5000)
        assert pts == 8

    def test_low_buffer(self):
        # 45 days
        pts, days, _ = _liquidity_score(7500, 5000)
        assert pts == 15

    def test_critical_buffer(self):
        # 15 days
        pts, days, _ = _liquidity_score(2500, 5000)
        assert pts == 25

    def test_zero_expense_returns_zero(self):
        pts, days, _ = _liquidity_score(10000, 0)
        assert pts == 0


class TestSavingsScore:
    def test_great_savings(self):
        pts, rate, _ = _savings_score(50000, 30000)
        assert pts == 0 and rate == pytest.approx(0.40)

    def test_moderate_savings(self):
        pts, rate, _ = _savings_score(50000, 43000)
        assert pts == 5

    def test_low_savings(self):
        pts, rate, _ = _savings_score(50000, 47000)
        assert pts == 10

    def test_deficit_spending(self):
        pts, rate, _ = _savings_score(30000, 35000)
        assert pts == 15 and rate < 0

    def test_zero_income(self):
        pts, rate, _ = _savings_score(0, 5000)
        assert pts == 15


# ── compute_risk_score() integration tests ────────────────────────────────────

class TestComputeRiskScore:

    def test_returns_risk_result(self):
        result = compute_risk_score(healthy_transactions())
        assert isinstance(result, RiskResult)

    def test_score_in_range(self):
        for txns in [healthy_transactions(), high_debt_transactions()]:
            result = compute_risk_score(txns)
            assert 0 <= result.score <= 100

    def test_healthy_saver_is_safe(self):
        result = compute_risk_score(healthy_transactions(), emi_monthly=0, current_balance=88700)
        assert result.score <= 25
        assert result.label == "Safe"

    def test_high_debt_user_is_high_risk(self):
        result = compute_risk_score(high_debt_transactions(), emi_monthly=15000, current_balance=2000)
        assert result.score >= 50
        assert result.label in ("High Risk", "Critical", "Moderate")

    def test_critical_emi_raises_score(self):
        low = compute_risk_score(healthy_transactions(), emi_monthly=0)
        high = compute_risk_score(healthy_transactions(), emi_monthly=40000)
        assert high.score > low.score

    def test_explanations_are_non_empty(self):
        result = compute_risk_score(healthy_transactions())
        assert len(result.explanations) == 4
        assert all(isinstance(e, str) and len(e) > 0 for e in result.explanations)

    def test_recommendations_are_non_empty(self):
        result = compute_risk_score(healthy_transactions())
        assert len(result.recommendations) >= 1

    def test_factor_scores_sum_equals_total(self):
        result = compute_risk_score(healthy_transactions(), emi_monthly=5000, current_balance=10000)
        assert sum(result.factor_scores.values()) == result.score

    def test_factor_keys_present(self):
        result = compute_risk_score(healthy_transactions())
        assert set(result.factors.keys()) == {
            "emi_ratio", "spending_cv", "buffer_days",
            "savings_rate", "monthly_income", "avg_monthly_expense"
        }

    def test_empty_transactions_returns_result(self):
        result = compute_risk_score([], emi_monthly=0, current_balance=0)
        assert isinstance(result, RiskResult)
        assert 0 <= result.score <= 100

    def test_balance_inferred_from_transactions(self):
        txns = healthy_transactions()
        result = compute_risk_score(txns)   # no current_balance passed
        assert result.factors["buffer_days"] > 0

    def test_high_debt_has_emi_recommendation(self):
        result = compute_risk_score(high_debt_transactions(), emi_monthly=20000, current_balance=1000)
        recs = " ".join(result.recommendations).lower()
        assert "emi" in recs or "loan" in recs or "emergency" in recs
