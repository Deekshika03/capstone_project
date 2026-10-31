import pandas as pd
from typing import Union
from pathlib import Path
from src.ingestion.transaction import Transaction


def parse_csv(source: Union[str, Path, object]) -> list[Transaction]:
    df = pd.read_csv(source)
    required = {"Date", "Description", "Amount", "Type"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {', '.join(missing)}")

    df.dropna(subset=["Date", "Amount", "Type"], inplace=True)
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
    df.dropna(subset=["Amount"], inplace=True)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df.dropna(subset=["Date"], inplace=True)
    df["Description"] = df["Description"].fillna("Unknown")

    transactions = []
    for _, row in df.iterrows():
        try:
            transactions.append(Transaction(
                date=row["Date"].date(),
                description=str(row["Description"]),
                amount=float(row["Amount"]),
                type=str(row["Type"]),
                source="csv",
            ))
        except Exception:
            continue
    return transactions
