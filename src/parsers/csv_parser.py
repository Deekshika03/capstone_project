import pandas as pd
from typing import List
from src.models.transaction import Transaction


# Accepted column name variants (lowercase) → standard field name
_COL_MAP = {
    "date":        "date",
    "amount":      "amount",
    "type":        "type",
    "transaction type": "type",
    "debit/credit": "type",
    "description": "description",
    "narration":   "description",
    "particulars": "description",
    "remarks":     "description",
    "balance":     "balance",
    "closing balance": "balance",
}


def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename raw CSV columns to standard names using _COL_MAP."""
    rename = {c: _COL_MAP[c.strip().lower()] for c in df.columns if c.strip().lower() in _COL_MAP}
    return df.rename(columns=rename)


def _infer_type(row: pd.Series) -> str:
    """
    If a 'type' column is missing, infer debit/credit from separate
    Debit/Credit columns that some banks export.
    """
    if "debit" in row and pd.notna(row["debit"]) and float(row["debit"]) > 0:
        return "debit"
    if "credit" in row and pd.notna(row["credit"]) and float(row["credit"]) > 0:
        return "credit"
    return "debit"  # fallback


def parse_csv(filepath: str) -> tuple[pd.DataFrame, List[Transaction]]:
    """
    Parse a bank statement CSV file.

    Returns:
        df            – clean pd.DataFrame with standard columns
        transactions  – list of validated Transaction Pydantic objects
    """
    raw = pd.read_csv(filepath)
    df = _normalise_columns(raw)

    # Handle banks that split amount into Debit / Credit columns
    if "amount" not in df.columns:
        if "debit" in df.columns or "credit" in df.columns:
            df["debit"]  = pd.to_numeric(df.get("debit",  0), errors="coerce").fillna(0)
            df["credit"] = pd.to_numeric(df.get("credit", 0), errors="coerce").fillna(0)
            df["amount"] = df["debit"] + df["credit"]
            if "type" not in df.columns:
                df["type"] = df.apply(_infer_type, axis=1)
        else:
            raise ValueError("CSV must contain an 'Amount' column or separate 'Debit'/'Credit' columns.")

    required = {"date", "amount", "type", "description"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # Clean & cast
    df["date"]        = pd.to_datetime(df["date"], errors="coerce")
    df["amount"]      = pd.to_numeric(df["amount"], errors="coerce").abs()
    df["type"]        = df["type"].str.strip().str.lower()
    df["description"] = df["description"].fillna("Unknown").str.strip()
    if "balance" in df.columns:
        df["balance"] = pd.to_numeric(df["balance"], errors="coerce")
    else:
        df["balance"] = None

    df.dropna(subset=["date", "amount", "type"], inplace=True)
    df.reset_index(drop=True, inplace=True)

    # Build Pydantic list
    transactions: List[Transaction] = []
    for _, row in df.iterrows():
        try:
            transactions.append(Transaction(
                date=row["date"].date(),
                amount=row["amount"],
                type=row["type"],
                description=row["description"],
                balance=row["balance"] if pd.notna(row["balance"]) else None,
            ))
        except Exception:
            continue  # skip rows that fail validation

    return df[["date", "amount", "type", "description", "balance"]], transactions
