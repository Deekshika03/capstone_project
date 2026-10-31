import re
import pdfplumber
from datetime import datetime
from typing import Union
from pathlib import Path
from src.ingestion.transaction import Transaction

_ROW_PATTERN = re.compile(
    r"(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})"
    r"\s+(.+?)\s+"
    r"(-?\d+(?:\.\d{1,2})?)"
    r"\s+(Income|Expense)",
    re.IGNORECASE,
)
_DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"]


def _parse_date(raw: str):
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unrecognised date format: {raw}")


def parse_pdf(source: Union[str, Path, object]) -> list[Transaction]:
    transactions = []
    with pdfplumber.open(source) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for match in _ROW_PATTERN.finditer(text):
                raw_date, desc, amount, txn_type = match.groups()
                try:
                    transactions.append(Transaction(
                        date=_parse_date(raw_date),
                        description=desc.strip(),
                        amount=float(amount),
                        type=txn_type.capitalize(),
                        source="pdf",
                    ))
                except Exception:
                    continue
    return transactions
