"""
verify_chunk3.py
Run: python verify_chunk3.py
Feeds 100 sample transactions through the categorizer and prints a full report.
"""

import json
from src.ingestion.csv_parser import parse_csv
from src.intelligence.categorizer import (
    categorize_transactions,
    monthly_burn_rate,
    discretionary_ratio,
    category_breakdown,
    flag_waste,
)

CSV_PATH = "tests/sample_100_transactions.csv"


def main():
    # 1. Parse
    transactions = parse_csv(CSV_PATH)
    print(f"✅ Loaded {len(transactions)} transactions\n")

    # 2. Categorize
    transactions = categorize_transactions(transactions)

    # 3. Category breakdown
    print("=" * 50)
    print("📊 CATEGORY BREAKDOWN")
    print("=" * 50)
    df_breakdown = category_breakdown(transactions)
    print(df_breakdown.to_string(index=False))

    # 4. Monthly burn rate
    print("\n" + "=" * 50)
    print("📈 MONTHLY BURN RATE")
    print("=" * 50)
    df_burn = monthly_burn_rate(transactions)
    print(df_burn.to_string(index=False))

    # 5. Discretionary ratio
    print("\n" + "=" * 50)
    print("💡 DISCRETIONARY vs NON-DISCRETIONARY")
    print("=" * 50)
    ratio = discretionary_ratio(transactions)
    print(f"  Discretionary:     ₹{ratio['discretionary']:,.2f}  ({ratio['discretionary_pct']}%)")
    print(f"  Non-Discretionary: ₹{ratio['non_discretionary']:,.2f}  ({ratio['non_discretionary_pct']}%)")

    # 6. Waste flags
    print("\n" + "=" * 50)
    print("🚨 FLAGGED ANOMALIES")
    print("=" * 50)
    flags = flag_waste(transactions)
    if flags:
        for f in flags:
            print(f"  [{f['type']}] {f['detail']}  |  Impact: ₹{f['impact']:,.2f}")
    else:
        print("  No anomalies detected.")

    # 7. Sample JSON output
    print("\n" + "=" * 50)
    print("🗂️  SAMPLE JSON RECORDS (first 5)")
    print("=" * 50)
    sample = [
        {**t.model_dump(), "date": t.date.isoformat()}
        for t in transactions[:5]
    ]
    print(json.dumps(sample, indent=2))


if __name__ == "__main__":
    main()
