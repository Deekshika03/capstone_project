"""
ocr_parser.py — Chunk 2
Extracts transactions from bill/receipt images using Pillow + pytesseract.
Pipeline: preprocess → OCR → extract fields → return list[Transaction]
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Union

import pytesseract
from PIL import Image, ImageFilter, ImageOps

from src.ingestion.transaction import Transaction

_DATE_PATTERNS = [
    r"\b(\d{4}-\d{2}-\d{2})\b",
    r"\b(\d{2}/\d{2}/\d{4})\b",
    r"\b(\d{2}-\d{2}-\d{4})\b",
    r"\b(\d{1,2}\s+\w{3}\s+\d{4})\b",
]
_DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%d %b %Y", "%d %B %Y"]

# Requires a currency label OR a decimal point to avoid matching bare integers
_AMOUNT_PATTERN = re.compile(
    r"(?:"
    r"(?:total|amount|amt|rs\.?|inr|\$|₹)\s*:?\s*([0-9,]+(?:\.[0-9]{1,2})?)"
    r"|([0-9,]+\.[0-9]{1,2})"
    r")",
    re.IGNORECASE,
)

_SKIP_LINE = re.compile(r"^\s*(\d[\d/\-\.]+\s*|\s*)$")


def preprocess_image(image: Image.Image) -> Image.Image:
    """Grayscale → resize → sharpen → binarize for better OCR accuracy."""
    img = ImageOps.grayscale(image)
    w, h = img.size
    if w < 1000:
        scale = 1000 / w
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    img = img.filter(ImageFilter.SHARPEN)
    img = img.point(lambda px: 255 if px > 140 else 0, "1")
    return img


def _extract_date(text: str):
    for pattern in _DATE_PATTERNS:
        match = re.search(pattern, text)
        if match:
            raw = match.group(1)
            for fmt in _DATE_FORMATS:
                try:
                    return datetime.strptime(raw, fmt).date()
                except ValueError:
                    continue
    return None


def _extract_amounts_from_matches(matches) -> list[float]:
    amounts = []
    for labelled, bare in matches:
        raw = labelled or bare
        try:
            val = float(raw.replace(",", ""))
            if 1900 <= val <= 2100 and val == int(val):
                continue
            amounts.append(val)
        except ValueError:
            continue
    return amounts


def _extract_amount(text: str) -> float | None:
    matches = _AMOUNT_PATTERN.findall(text)
    amounts = _extract_amounts_from_matches(matches)
    return max(amounts) if amounts else None


def _extract_vendor(lines: list[str]) -> str:
    for line in lines:
        line = line.strip()
        if line and not _SKIP_LINE.match(line) and len(line) > 2:
            return line
    return "Unknown Vendor"


def _infer_type(text: str, amount) -> str:
    lower = text.lower()
    income_keywords = ["salary", "credit", "refund", "cashback", "deposit", "payment received"]
    if any(kw in lower for kw in income_keywords):
        return "Income"
    return "Expense"


def parse_image(source: Union[str, Path, Image.Image, object]) -> list[Transaction]:
    """Extract a transaction from a receipt/bill image."""
    image = source if isinstance(source, Image.Image) else Image.open(source)
    processed = preprocess_image(image)
    raw_text = pytesseract.image_to_string(processed, config="--psm 6")

    if not raw_text.strip():
        raise ValueError("OCR extracted no text from the image. Try a clearer photo.")

    lines = [l for l in raw_text.splitlines() if l.strip()]
    txn_date = _extract_date(raw_text)
    amount   = _extract_amount(raw_text)
    vendor   = _extract_vendor(lines)
    txn_type = _infer_type(raw_text, amount)

    if txn_date is None:
        raise ValueError("Could not find a date in the image. Ensure the receipt shows a clear date.")
    if amount is None:
        raise ValueError("Could not find an amount in the image. Ensure the total amount is visible.")

    return [Transaction(
        date=txn_date,
        description=vendor,
        amount=-abs(amount) if txn_type == "Expense" else abs(amount),
        type=txn_type,
        source="ocr",
    )]


def parse_image_raw_text(source: Union[str, Path, Image.Image, object]) -> str:
    """Return raw OCR text for debugging."""
    image = source if isinstance(source, Image.Image) else Image.open(source)
    processed = preprocess_image(image)
    return pytesseract.image_to_string(processed, config="--psm 6")
