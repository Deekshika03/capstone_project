import json
import pytest
import pandas as pd
from datetime import date
from unittest.mock import patch, MagicMock

from src.models.transaction import Transaction
from src.parsers.csv_parser import parse_csv
from src.parsers.pdf_parser import parse_pdf

MOCK_CSV = "tests/mock_bank_statement.csv"


# ── Transaction model tests ───────────────────────────────────────────────────

class TestTransactionModel:

    def test_valid_transaction(self):
        t = Transaction(date=date(2024, 1, 5), amount=5000.0, type="credit",
                        description="Salary Credit", balance=5000.0)
        assert t.type == "credit"
        assert t.amount == 5000.0

    def test_type_normalised_to_lowercase(self):
        t = Transaction(date=date(2024, 1, 7), amount=12.5, type="Debit",
                        description="Uber Ride")
        assert t.type == "debit"

    def test_invalid_type_raises(self):
        with pytest.raises(Exception):
            Transaction(date=date(2024, 1, 7), amount=12.5, type="unknown",
                        description="Test")

    def test_negative_amount_raises(self):
        with pytest.raises(Exception):
            Transaction(date=date(2024, 1, 7), amount=-50.0, type="debit",
                        description="Test")

    def test_balance_optional(self):
        t = Transaction(date=date(2024, 1, 7), amount=12.5, type="debit",
                        description="Uber Ride")
        assert t.balance is None

    def test_to_dict(self):
        t = Transaction(date=date(2024, 1, 5), amount=5000.0, type="credit",
                        description="Salary", balance=5000.0)
        d = t.to_dict()
        assert d["date"] == "2024-01-05"
        assert d["type"] == "credit"


# ── CSV parser tests ──────────────────────────────────────────────────────────

class TestCSVParser:

    def test_returns_dataframe_and_list(self):
        df, transactions = parse_csv(MOCK_CSV)
        assert isinstance(df, pd.DataFrame)
        assert isinstance(transactions, list)

    def test_correct_row_count(self):
        df, transactions = parse_csv(MOCK_CSV)
        assert len(df) == 10
        assert len(transactions) == 10

    def test_standard_columns_present(self):
        df, _ = parse_csv(MOCK_CSV)
        assert set(df.columns) == {"date", "amount", "type", "description", "balance"}

    def test_all_transactions_are_pydantic(self):
        _, transactions = parse_csv(MOCK_CSV)
        assert all(isinstance(t, Transaction) for t in transactions)

    def test_amounts_are_positive(self):
        df, _ = parse_csv(MOCK_CSV)
        assert (df["amount"] >= 0).all()

    def test_types_are_valid(self):
        df, _ = parse_csv(MOCK_CSV)
        assert df["type"].isin(["debit", "credit"]).all()

    def test_json_serialisable(self):
        _, transactions = parse_csv(MOCK_CSV)
        records = [t.to_dict() for t in transactions]
        json_str = json.dumps(records)   # must not raise
        assert len(json.loads(json_str)) == 10

    def test_missing_required_column_raises(self, tmp_path):
        bad_csv = tmp_path / "bad.csv"
        bad_csv.write_text("Date,Amount\n2024-01-01,100\n")
        with pytest.raises(ValueError, match="Missing required columns"):
            parse_csv(str(bad_csv))

    def test_invalid_amounts_dropped(self, tmp_path):
        csv = tmp_path / "partial.csv"
        csv.write_text(
            "Date,Description,Amount,Type,Balance\n"
            "2024-01-01,Valid,100.00,debit,900.00\n"
            "2024-01-02,Invalid,abc,debit,\n"
        )
        df, transactions = parse_csv(str(csv))
        assert len(df) == 1
        assert len(transactions) == 1


# ── PDF parser tests (mocked) ─────────────────────────────────────────────────

class TestPDFParser:

    def _make_mock_pdf(self, tables=None, text=""):
        """Build a mock pdfplumber PDF object."""
        page = MagicMock()
        page.extract_tables.return_value = tables or []
        page.extract_text.return_value = text
        pdf = MagicMock()
        pdf.__enter__ = MagicMock(return_value=pdf)
        pdf.__exit__ = MagicMock(return_value=False)
        pdf.pages = [page]
        return pdf

    def test_pdf_table_extraction(self):
        table = [
            ["Date", "Description", "Amount", "Type", "Balance"],
            ["2024-01-05", "Salary Credit", "5000.00", "credit", "5000.00"],
            ["2024-01-07", "Uber Ride",     "12.50",   "debit",  "4987.50"],
        ]
        mock_pdf = self._make_mock_pdf(tables=[table])
        with patch("pdfplumber.open", return_value=mock_pdf):
            df, transactions = parse_pdf("fake.pdf")
        assert len(df) == 2
        assert len(transactions) == 2
        assert all(isinstance(t, Transaction) for t in transactions)

    def test_pdf_text_fallback(self):
        text = (
            "05/01/2024  Salary Credit  5000.00\n"
            "07/01/2024  Uber Ride       12.50\n"
        )
        mock_pdf = self._make_mock_pdf(tables=[], text=text)
        with patch("pdfplumber.open", return_value=mock_pdf):
            df, transactions = parse_pdf("fake.pdf")
        assert len(df) >= 1

    def test_empty_pdf_raises(self):
        mock_pdf = self._make_mock_pdf(tables=[], text="")
        with patch("pdfplumber.open", return_value=mock_pdf):
            with pytest.raises(ValueError, match="No transaction data"):
                parse_pdf("fake.pdf")

    def test_pdf_output_json_serialisable(self):
        table = [
            ["Date", "Description", "Amount", "Type", "Balance"],
            ["2024-01-05", "Salary", "5000.00", "credit", "5000.00"],
        ]
        mock_pdf = self._make_mock_pdf(tables=[table])
        with patch("pdfplumber.open", return_value=mock_pdf):
            _, transactions = parse_pdf("fake.pdf")
        records = [t.to_dict() for t in transactions]
        json.dumps(records)   # must not raise
