import re
import pdfplumber
import pandas as pd
from typing import List
from src.models.transaction import Transaction


# Regex patterns to detect date and amount in raw text lines
_DATE_RE   = re.compile(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})\b")
_AMOUNT_RE = re.compile(r"\b\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?\b")


def _parse_table(table: list) -> pd.DataFrame | None:
    """Convert a pdfplumber table (list of lists) into a normalised DataFrame."""
    if not table or len(table) < 2:
        return None

    headers = [str(h).strip().lower() if h else "" for h in table[0]]
    rows = table[1:]

    df = pd.DataFrame(rows, columns=headers)
    df.replace("", pd.NA, inplace=True)
    df.dropna(how="all", inplace=True)

    # Map common PDF header names to standard fields
    col_map = {
        "date": "date", "txn date": "date", "value date": "date",
        "transaction date": "date",
        "description": "description", "narration": "description",
        "particulars": "description", "details": "description",
        "amount": "amount", "debit": "debit", "credit": "credit",
        "balance": "balance", "closing balance": "balance",
        "type": "type", "dr/cr": "type",
    }
    df.rename(columns={c: col_map[c] for c in df.columns if c in col_map}, inplace=True)
    return df


def _df_from_text(text: str) -> pd.DataFrame:
    """
    Fallback: extract transactions line-by-line from raw PDF text
    when no structured table is found.
    """
    records = []
    for line in text.splitlines():
        line = line.strip()
        date_match   = _DATE_RE.search(line)
        amount_match = _AMOUNT_RE.findall(line)
        if date_match and amount_match:
            records.append({
                "date":        date_match.group(),
                "amount":      amount_match[-1].replace(",", ""),
                "description": line,
                "type":        "debit",   # unknown from plain text; default
                "balance":     None,
            })
    return pd.DataFrame(records) if records else pd.DataFrame()


def _finalise(df: pd.DataFrame) -> tuple[pd.DataFrame, List[Transaction]]:
    """Clean, cast, and build Pydantic list from a raw parsed DataFrame."""

    # Handle split debit/credit columns
    if "amount" not in df.columns:
        df["debit"]  = pd.to_numeric(df.get("debit",  pd.Series(dtype=float)), errors="coerce").fillna(0)
        df["credit"] = pd.to_numeric(df.get("credit", pd.Series(dtype=float)), errors="coerce").fillna(0)
        df["amount"] = df["debit"] + df["credit"]
        if "type" not in df.columns:
            df["type"] = df.apply(
                lambda r: "credit" if r["credit"] > 0 else "debit", axis=1
            )

    if "date" not in df.columns or "amount" not in df.columns:
        return pd.DataFrame(), []

    df["date"]        = pd.to_datetime(df["date"], errors="coerce")
    df["amount"]      = pd.to_numeric(df["amount"].astype(str).str.replace(",", ""), errors="coerce").abs()
    df["description"] = df.get("description", pd.Series("Unknown", index=df.index)).fillna("Unknown").astype(str).str.strip()
    df["type"]        = df.get("type", pd.Series("debit", index=df.index)).fillna("debit").astype(str).str.strip().str.lower()
    df["balance"]     = pd.to_numeric(df.get("balance", pd.Series(dtype=float)), errors="coerce")

    df.dropna(subset=["date", "amount"], inplace=True)
    df.reset_index(drop=True, inplace=True)

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
            continue

    return df[["date", "amount", "type", "description", "balance"]], transactions


def parse_pdf(filepath: str) -> tuple[pd.DataFrame, List[Transaction]]:
    """
    Parse a digital bank statement PDF.

    Tries structured table extraction first (pdfplumber);
    falls back to regex-based line parsing if no tables found.

    Returns:
        df            – clean pd.DataFrame with standard columns
        transactions  – list of validated Transaction Pydantic objects
    """
    all_frames: list[pd.DataFrame] = []

    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            if tables:
                for table in tables:
                    df = _parse_table(table)
                    if df is not None:
                        all_frames.append(df)
            else:
                text = page.extract_text() or ""
                df = _df_from_text(text)
                if not df.empty:
                    all_frames.append(df)

    if not all_frames:
        raise ValueError("No transaction data could be extracted from the PDF.")

    combined = pd.concat(all_frames, ignore_index=True)
    return _finalise(combined)
