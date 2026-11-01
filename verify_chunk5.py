"""
verify_chunk5.py
Run: python verify_chunk5.py
Tests two scenarios — healthy saver vs high debt user — and prints full risk reports.
"""

from datetime import date
from src.ingestion.transaction import Transaction
from src.intelligence.risk_engine import compute_risk_score


def make_txn(desc, amount, txn_type, txn_date, balance=None):
    t = Transaction(date=txn_date, description=desc, amount=amount, type=txn_type)
    if balance is not None:
        t = t.model_copy(update={"balance": balance})
    return t


SCENARIOS = {
    "🟢 Healthy Saver": {
        "transactions": [
            make_txn("Salary",    50000, "Income",  date(2024, 1, 1),  balance=50000),
            make_txn("Grocery",   -3000, "Expense", date(2024, 1, 5),  balance=47000),
            make_txn("Utilities", -1500, "Expense", date(2024, 1, 10), balance=45500),
            make_txn("Transport", -1000, "Expense", date(2024, 1, 15), balance=44500),
            make_txn("Salary",    50000, "Income",  date(2024, 2, 1),  balance=94500),
            make_txn("Grocery",   -3200, "Expense", date(2024, 2, 5),  balance=91300),
            make_txn("Utilities", -1500, "Expense", date(2024, 2, 10), balance=89800),
            make_txn("Transport", -1100, "Expense", date(2024, 2, 15), balance=88700),
            make_txn("Salary",    50000, "Income",  date(2024, 3, 1),  balance=138700),
            make_txn("Grocery",   -3100, "Expense", date(2024, 3, 5),  balance=135600),
            make_txn("Utilities", -1500, "Expense", date(2024, 3, 10), balance=134100),
        ],
        "emi_monthly":     0,
        "current_balance": 134100,
    },
    "🔴 High Debt User": {
        "transactions": [
            make_txn("Salary",    30000, "Income",  date(2024, 1, 1),  balance=5000),
            make_txn("EMI Loan", -15000, "Expense", date(2024, 1, 3),  balance=-10000),
            make_txn("Grocery",   -5000, "Expense", date(2024, 1, 10), balance=-15000),
            make_txn("Shopping",  -4000, "Expense", date(2024, 1, 20), balance=-19000),
            make_txn("Salary",    30000, "Income",  date(2024, 2, 1),  balance=11000),
            make_txn("EMI Loan", -15000, "Expense", date(2024, 2, 3),  balance=-4000),
            make_txn("Grocery",   -8000, "Expense", date(2024, 2, 10), balance=-12000),
            make_txn("Salary",    30000, "Income",  date(2024, 3, 1),  balance=18000),
            make_txn("EMI Loan", -15000, "Expense", date(2024, 3, 3),  balance=3000),
            make_txn("Grocery",   -3000, "Expense", date(2024, 3, 10), balance=0),
        ],
        "emi_monthly":     15000,
        "current_balance": 2000,
    },
    "🟡 Moderate Risk User": {
        "transactions": [
            make_txn("Salary",    40000, "Income",  date(2024, 1, 1),  balance=15000),
            make_txn("EMI Loan",  -8000, "Expense", date(2024, 1, 3),  balance=7000),
            make_txn("Grocery",   -4000, "Expense", date(2024, 1, 10), balance=3000),
            make_txn("Shopping", -10000, "Expense", date(2024, 1, 20), balance=-7000),
            make_txn("Salary",    40000, "Income",  date(2024, 2, 1),  balance=33000),
            make_txn("EMI Loan",  -8000, "Expense", date(2024, 2, 3),  balance=25000),
            make_txn("Grocery",   -4500, "Expense", date(2024, 2, 10), balance=20500),
            make_txn("Dining",    -2000, "Expense", date(2024, 2, 20), balance=18500),
        ],
        "emi_monthly":     8000,
        "current_balance": 18500,
    },
}


def print_report(name: str, result) -> None:
    print(f"\n{'='*55}")
    print(f"  {name}")
    print(f"{'='*55}")
    print(f"  Risk Score : {result.score} / 100")
    print(f"  Label      : {result.label}")
    print(f"\n  📊 Factor Scores:")
    for factor, pts in result.factor_scores.items():
        print(f"     {factor:<20} {pts:>3} pts")
    print(f"\n  📋 Key Metrics:")
    print(f"     Monthly Income      : ₹{result.factors['monthly_income']:,.0f}")
    print(f"     Avg Monthly Expense : ₹{result.factors['avg_monthly_expense']:,.0f}")
    print(f"     EMI Ratio           : {result.factors['emi_ratio']*100:.1f}%")
    print(f"     Savings Rate        : {result.factors['savings_rate']*100:.1f}%")
    print(f"     Buffer Days         : {result.factors['buffer_days']:.0f} days")
    print(f"     Spending CV         : {result.factors['spending_cv']:.3f}")
    print(f"\n  💬 Explanations:")
    for exp in result.explanations:
        print(f"     {exp}")
    print(f"\n  🎯 Recommendations:")
    for rec in result.recommendations:
        print(f"     → {rec}")


def main():
    print("\n🏦 FinGuard AI — Financial Risk Score Report")
    for name, config in SCENARIOS.items():
        result = compute_risk_score(
            transactions=config["transactions"],
            emi_monthly=config["emi_monthly"],
            current_balance=config["current_balance"],
        )
        print_report(name, result)
    print(f"\n{'='*55}\n")


if __name__ == "__main__":
    main()
