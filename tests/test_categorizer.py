import pytest
from datetime import date
from src.ingestion.transaction import Transaction
from src.intelligence.categorizer import (
    classify,
    categorize_transactions,
    monthly_burn_rate,
    discretionary_ratio,
    category_breakdown,
    flag_waste,
    DISCRETIONARY,
    NON_DISCRETIONARY,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_txn(desc, amount, txn_type="Expense", txn_date=date(2024, 1, 10), category=None):
    t = Transaction(date=txn_date, description=desc, amount=amount, type=txn_type)
    if category:
        t = t.model_copy(update={"category": category})
    return t


# ── classify() ────────────────────────────────────────────────────────────────

class TestClassify:
    def test_groceries(self):
        assert classify("Big Bazaar Grocery") == "Groceries"

    def test_healthcare(self):
        assert classify("Apollo Pharmacy") == "Healthcare"

    def test_utilities(self):
        assert classify("Airtel Broadband Bill") == "Utilities"

    def test_investment(self):
        assert classify("Zerodha SIP Investment") == "Investment"

    def test_entertainment(self):
        assert classify("Netflix Subscription") == "Entertainment"

    def test_transport(self):
        assert classify("Uber Ride") == "Transport"

    def test_food_dining(self):
        assert classify("Zomato Food Delivery") == "Food & Dining"

    def test_shopping(self):
        assert classify("Amazon Shopping") == "Shopping"

    def test_ml_fallback_returns_string(self):
        result = classify("completely unknown random vendor xyz")
        assert isinstance(result, str) and len(result) > 0


# ── categorize_transactions() ─────────────────────────────────────────────────

class TestCategorizeTransactions:
    def test_all_transactions_get_category(self):
        txns = [
            make_txn("Netflix Subscription", -649),
            make_txn("Uber Ride", -180),
            make_txn("Apollo Pharmacy", -520),
        ]
        result = categorize_transactions(txns)
        assert all(t.category is not None for t in result)

    def test_correct_categories_assigned(self):
        txns = [
            make_txn("Netflix Subscription", -649),
            make_txn("Apollo Pharmacy", -520),
            make_txn("Zerodha SIP Investment", -5000),
        ]
        result = categorize_transactions(txns)
        cats = [t.category for t in result]
        assert "Entertainment" in cats
        assert "Healthcare" in cats
        assert "Investment" in cats

    def test_original_transactions_not_mutated(self):
        txn = make_txn("Netflix Subscription", -649)
        original_cat = txn.category
        categorize_transactions([txn])
        assert txn.category == original_cat


# ── monthly_burn_rate() ───────────────────────────────────────────────────────

class TestMonthlyBurnRate:
    def test_returns_dataframe(self):
        txns = [
            make_txn("Grocery", -1000, txn_date=date(2024, 1, 5)),
            make_txn("Grocery", -1200, txn_date=date(2024, 2, 5)),
        ]
        df = monthly_burn_rate(txns)
        assert list(df.columns) == ["month", "total_spent", "burn_rate_change_pct"]

    def test_correct_month_count(self):
        txns = [
            make_txn("A", -500, txn_date=date(2024, 1, 1)),
            make_txn("B", -600, txn_date=date(2024, 2, 1)),
            make_txn("C", -700, txn_date=date(2024, 3, 1)),
        ]
        df = monthly_burn_rate(txns)
        assert len(df) == 3

    def test_income_excluded(self):
        txns = [
            make_txn("Salary", 50000, txn_type="Income", txn_date=date(2024, 1, 1)),
            make_txn("Grocery", -1000, txn_date=date(2024, 1, 5)),
        ]
        df = monthly_burn_rate(txns)
        assert df["total_spent"].iloc[0] == 1000

    def test_empty_returns_empty_df(self):
        df = monthly_burn_rate([])
        assert df.empty

    def test_burn_rate_increase(self):
        txns = [
            make_txn("A", -1000, txn_date=date(2024, 1, 1)),
            make_txn("B", -2000, txn_date=date(2024, 2, 1)),
        ]
        df = monthly_burn_rate(txns)
        assert df["burn_rate_change_pct"].iloc[1] == pytest.approx(100.0)


# ── discretionary_ratio() ─────────────────────────────────────────────────────

class TestDiscretionaryRatio:
    def test_returns_all_keys(self):
        txns = [make_txn("Netflix", -649, category="Entertainment")]
        result = discretionary_ratio(txns)
        assert all(k in result for k in
                   ["discretionary", "non_discretionary", "discretionary_pct", "non_discretionary_pct"])

    def test_entertainment_is_discretionary(self):
        txns = [make_txn("Netflix", -649, category="Entertainment")]
        result = discretionary_ratio(txns)
        assert result["discretionary"] == 649

    def test_healthcare_is_non_discretionary(self):
        txns = [make_txn("Apollo", -500, category="Healthcare")]
        result = discretionary_ratio(txns)
        assert result["non_discretionary"] == 500

    def test_percentages_sum_to_100(self):
        txns = [
            make_txn("Netflix", -500, category="Entertainment"),
            make_txn("Apollo", -500, category="Healthcare"),
        ]
        result = discretionary_ratio(txns)
        assert result["discretionary_pct"] + result["non_discretionary_pct"] == pytest.approx(100.0)


# ── category_breakdown() ──────────────────────────────────────────────────────

class TestCategoryBreakdown:
    def test_returns_dataframe(self):
        txns = [make_txn("Netflix", -649, category="Entertainment")]
        df = category_breakdown(txns)
        assert list(df.columns) == ["category", "total"]

    def test_sorted_descending(self):
        txns = [
            make_txn("Netflix", -649, category="Entertainment"),
            make_txn("Grocery", -2000, category="Groceries"),
        ]
        df = category_breakdown(txns)
        assert df["total"].iloc[0] >= df["total"].iloc[1]

    def test_income_excluded(self):
        txns = [
            make_txn("Salary", 50000, txn_type="Income", category="Other"),
            make_txn("Netflix", -649, category="Entertainment"),
        ]
        df = category_breakdown(txns)
        assert len(df) == 1


# ── flag_waste() ──────────────────────────────────────────────────────────────

class TestFlagWaste:
    def test_flags_multiple_subscriptions(self):
        txns = [
            make_txn("Netflix Subscription", -649, category="Entertainment"),
            make_txn("Spotify Premium", -119, category="Entertainment"),
            make_txn("Hotstar Subscription", -299, category="Entertainment"),
        ]
        flags = flag_waste(txns)
        types = [f["type"] for f in flags]
        assert "Multiple Subscriptions" in types

    def test_no_flag_for_two_subscriptions(self):
        txns = [
            make_txn("Netflix Subscription", -649, category="Entertainment"),
            make_txn("Spotify Premium", -119, category="Entertainment"),
        ]
        flags = flag_waste(txns)
        types = [f["type"] for f in flags]
        assert "Multiple Subscriptions" not in types

    def test_flags_repeat_micro_transactions(self):
        txns = [
            make_txn("Starbucks Coffee", -320, txn_date=date(2024, 1, d))
            for d in [5, 10, 15, 20]
        ]
        flags = flag_waste(txns)
        types = [f["type"] for f in flags]
        assert "Repeat Micro-Transaction" in types

    def test_no_flag_for_three_microtxns(self):
        txns = [
            make_txn("Starbucks Coffee", -320, txn_date=date(2024, 1, d))
            for d in [5, 10, 15]
        ]
        flags = flag_waste(txns)
        types = [f["type"] for f in flags]
        assert "Repeat Micro-Transaction" not in types

    def test_returns_list(self):
        assert isinstance(flag_waste([]), list)
