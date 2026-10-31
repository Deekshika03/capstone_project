import io
import pytest
from datetime import date
from unittest.mock import patch
from PIL import Image

from src.ingestion.transaction import Transaction
from src.ingestion.csv_parser import parse_csv
from src.ingestion.ocr_parser import (
    preprocess_image, _extract_date, _extract_amount, _extract_vendor, _infer_type,
)


class TestTransaction:
    def test_valid_expense(self):
        t = Transaction(date=date(2024, 1, 5), description="Uber Ride", amount=-12.5, type="Expense")
        assert t.type == "Expense" and t.amount == -12.5

    def test_valid_income(self):
        t = Transaction(date=date(2024, 1, 1), description="Salary", amount=5000.0, type="Income")
        assert t.type == "Income"

    def test_type_case_insensitive(self):
        assert Transaction(date=date(2024,1,1), description="X", amount=100, type="income").type == "Income"

    def test_invalid_type_raises(self):
        with pytest.raises(Exception):
            Transaction(date=date(2024,1,1), description="X", amount=100, type="Transfer")

    def test_empty_description_defaults_to_unknown(self):
        assert Transaction(date=date(2024,1,1), description="  ", amount=100, type="Income").description == "Unknown"

    def test_default_category_is_other(self):
        assert Transaction(date=date(2024,1,1), description="X", amount=50, type="Expense").category == "Other"


class TestCSVParser:
    def _csv(self, content): return io.StringIO(content)

    def test_valid_csv(self):
        result = parse_csv(self._csv("Date,Description,Amount,Type\n2024-01-05,Salary,5000,Income\n2024-01-07,Uber,-12.50,Expense\n"))
        assert len(result) == 2 and result[0].type == "Income"

    def test_missing_column_raises(self):
        with pytest.raises(ValueError, match="Missing columns"):
            parse_csv(self._csv("Date,Description,Amount\n2024-01-01,Test,100\n"))

    def test_invalid_amount_rows_skipped(self):
        result = parse_csv(self._csv("Date,Description,Amount,Type\n2024-01-05,Salary,5000,Income\n2024-01-07,Bad,abc,Expense\n"))
        assert len(result) == 1

    def test_invalid_date_rows_skipped(self):
        result = parse_csv(self._csv("Date,Description,Amount,Type\nnot-a-date,Salary,5000,Income\n2024-01-07,Uber,-12.50,Expense\n"))
        assert len(result) == 1

    def test_source_is_csv(self):
        result = parse_csv(self._csv("Date,Description,Amount,Type\n2024-01-05,Salary,5000,Income\n"))
        assert result[0].source == "csv"

    def test_empty_csv_returns_empty_list(self):
        assert parse_csv(self._csv("Date,Description,Amount,Type\n")) == []


class TestOCRHelpers:
    def test_extract_date_iso(self):
        assert _extract_date("Invoice Date: 2024-03-15") == date(2024, 3, 15)

    def test_extract_date_slash(self):
        assert _extract_date("Date: 15/03/2024") == date(2024, 3, 15)

    def test_extract_date_none(self):
        assert _extract_date("No date here at all") is None

    def test_extract_amount_with_label(self):
        assert _extract_amount("Total: $125.50") == 125.50

    def test_extract_amount_returns_largest(self):
        assert _extract_amount("Item 10.00\nTax 5.00\nTotal 15.00") == 15.00

    def test_extract_amount_none(self):
        assert _extract_amount("No numbers here") is None

    def test_extract_vendor_skips_dates(self):
        assert _extract_vendor(["2024-01-01", "Starbucks Coffee", "Total: $6.75"]) == "Starbucks Coffee"

    def test_infer_type_salary_is_income(self):
        assert _infer_type("Salary credit for January", 5000) == "Income"

    def test_infer_type_default_expense(self):
        assert _infer_type("Thank you for your purchase", 50) == "Expense"

    def test_preprocess_returns_image(self):
        assert isinstance(preprocess_image(Image.new("RGB", (200, 200), color=200)), Image.Image)


class TestParseImage:
    def test_parse_image_returns_transaction(self):
        fake_text = "Starbucks Coffee\n2024-03-10\nTotal Amount: $6.75"
        img = Image.new("RGB", (400, 200), color=255)
        with patch("pytesseract.image_to_string", return_value=fake_text):
            from src.ingestion.ocr_parser import parse_image
            result = parse_image(img)
        assert len(result) == 1
        assert result[0].source == "ocr"
        assert result[0].amount == -6.75
        assert result[0].date == date(2024, 3, 10)

    def test_parse_image_raises_on_empty_ocr(self):
        img = Image.new("RGB", (400, 200), color=255)
        with patch("pytesseract.image_to_string", return_value="   "):
            from src.ingestion.ocr_parser import parse_image
            with pytest.raises(ValueError, match="no text"):
                parse_image(img)
