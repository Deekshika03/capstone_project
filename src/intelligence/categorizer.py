"""
categorizer.py — Chunk 3
Classifies transactions into categories, computes spending trends,
discretionary vs non-discretionary ratio, and flags wasteful patterns.

Pipeline:
  1. Keyword/regex rules  (fast, high-confidence)
  2. TF-IDF + LogisticRegression fallback (for unknown descriptions)
"""

import re
from collections import defaultdict
from datetime import date
from typing import Optional

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from src.ingestion.transaction import Transaction

# ── Category definitions ──────────────────────────────────────────────────────

CATEGORIES = [
    "Groceries",
    "Healthcare",
    "Utilities",
    "Investment",
    "Entertainment",
    "Transport",
    "Food & Dining",
    "Shopping",
    "Wasteful",
    "Other",
]

DISCRETIONARY = {"Entertainment", "Shopping", "Wasteful", "Food & Dining", "Other"}
NON_DISCRETIONARY = {"Groceries", "Healthcare", "Utilities", "Investment", "Transport"}

_RULES: list[tuple[str, list[str]]] = [
    ("Groceries",      ["grocery", "supermarket", "bigbasket", "dmart", "reliance fresh",
                        "nature's basket", "whole foods", "walmart grocery", "safeway"]),
    ("Healthcare",     ["pharmacy", "hospital", "clinic", "doctor", "medical", "apollo",
                        "chemist", "health", "dental", "lab test", "diagnostic"]),
    ("Utilities",      ["electric", "electricity", "water bill", "gas bill", "internet",
                        "broadband", "wifi", "phone bill", "mobile recharge", "dth",
                        "utility", "municipal"]),
    ("Investment",     ["mutual fund", "sip", "stock", "zerodha", "groww", "nps",
                        "insurance premium", "lic", "fd", "fixed deposit", "investment",
                        "trading", "brokerage"]),
    ("Entertainment",  ["netflix", "spotify", "prime video", "hotstar", "youtube premium",
                        "movie", "cinema", "concert", "gaming", "steam", "xbox", "playstation",
                        "subscription", "zee5", "apple tv"]),
    ("Transport",      ["uber", "ola", "lyft", "taxi", "cab", "metro", "bus pass",
                        "fuel", "petrol", "diesel", "gas station", "parking", "toll",
                        "rapido", "auto"]),
    ("Food & Dining",  ["zomato", "swiggy", "restaurant", "cafe", "coffee", "starbucks",
                        "mcdonald", "kfc", "pizza", "burger", "dining", "food delivery",
                        "dominos", "subway"]),
    ("Shopping",       ["amazon", "flipkart", "myntra", "ajio", "clothing", "fashion",
                        "mall", "store", "shop", "meesho", "nykaa", "electronics"]),
]

# ── Training data for TF-IDF fallback ────────────────────────────────────────

_TRAIN_X = [
    "big bazaar purchase", "reliance smart grocery", "vegetable market",
    "apollo pharmacy", "max hospital bill", "lab diagnostic test",
    "bescom electricity", "airtel broadband", "jio recharge",
    "zerodha brokerage", "sip mutual fund hdfc", "lic premium",
    "netflix monthly", "bookmyshow movie", "spotify subscription",
    "uber ride", "ola cab", "petrol pump fill",
    "zomato order", "swiggy delivery", "starbucks coffee",
    "amazon purchase", "flipkart order", "myntra clothing",
    "random misc payment", "unknown transfer", "other expense",
]
_TRAIN_Y = [
    "Groceries", "Groceries", "Groceries",
    "Healthcare", "Healthcare", "Healthcare",
    "Utilities", "Utilities", "Utilities",
    "Investment", "Investment", "Investment",
    "Entertainment", "Entertainment", "Entertainment",
    "Transport", "Transport", "Transport",
    "Food & Dining", "Food & Dining", "Food & Dining",
    "Shopping", "Shopping", "Shopping",
    "Other", "Other", "Other",
]

_classifier: Optional[Pipeline] = None


def _get_classifier() -> Pipeline:
    global _classifier
    if _classifier is None:
        _classifier = Pipeline([
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1)),
            ("lr",    LogisticRegression(max_iter=500)),
        ])
        _classifier.fit(_TRAIN_X, _TRAIN_Y)
    return _classifier


# ── Core classification ───────────────────────────────────────────────────────

def classify(description: str) -> str:
    """Return category for a transaction description using rules then ML fallback."""
    desc = description.lower()
    for category, keywords in _RULES:
        if any(re.search(rf"\b{re.escape(kw)}\b", desc) for kw in keywords):
            return category
    return _get_classifier().predict([desc])[0]


def categorize_transactions(transactions: list[Transaction]) -> list[Transaction]:
    """Return transactions with category field populated."""
    result = []
    for t in transactions:
        cat = classify(t.description)
        result.append(t.model_copy(update={"category": cat}))
    return result


# ── Spending trends ───────────────────────────────────────────────────────────

def monthly_burn_rate(transactions: list[Transaction]) -> pd.DataFrame:
    """Month-over-month total expense and burn rate change (%)."""
    rows = [
        {"month": t.date.strftime("%Y-%m"), "amount": abs(t.amount)}
        for t in transactions if t.type == "Expense"
    ]
    if not rows:
        return pd.DataFrame(columns=["month", "total_spent", "burn_rate_change_pct"])

    df = (
        pd.DataFrame(rows)
        .groupby("month")["amount"]
        .sum()
        .reset_index()
        .rename(columns={"amount": "total_spent"})
        .sort_values("month")
    )
    df["burn_rate_change_pct"] = df["total_spent"].pct_change() * 100
    return df.reset_index(drop=True)


def discretionary_ratio(transactions: list[Transaction]) -> dict:
    """Return discretionary vs non-discretionary spending ratio."""
    disc = sum(abs(t.amount) for t in transactions
               if t.type == "Expense" and t.category in DISCRETIONARY)
    non_disc = sum(abs(t.amount) for t in transactions
                   if t.type == "Expense" and t.category in NON_DISCRETIONARY)
    total = disc + non_disc or 1
    return {
        "discretionary":     round(disc, 2),
        "non_discretionary": round(non_disc, 2),
        "discretionary_pct": round(disc / total * 100, 1),
        "non_discretionary_pct": round(non_disc / total * 100, 1),
    }


def category_breakdown(transactions: list[Transaction]) -> pd.DataFrame:
    """Total spending per category for expense transactions."""
    rows = [
        {"category": t.category, "amount": abs(t.amount)}
        for t in transactions if t.type == "Expense"
    ]
    if not rows:
        return pd.DataFrame(columns=["category", "total"])
    return (
        pd.DataFrame(rows)
        .groupby("category")["amount"]
        .sum()
        .reset_index()
        .rename(columns={"amount": "total"})
        .sort_values("total", ascending=False)
        .reset_index(drop=True)
    )


# ── Waste detection ───────────────────────────────────────────────────────────

def flag_waste(transactions: list[Transaction]) -> list[dict]:
    """
    Detect wasteful patterns:
    - Multiple active subscriptions (Entertainment ≥ 3)
    - Repeat micro-transactions (same vendor, amount < 200, ≥ 4 times/month)
    """
    flags = []
    expenses = [t for t in transactions if t.type == "Expense"]

    # 1. Multiple subscriptions
    subs = [t for t in expenses if t.category == "Entertainment"]
    unique_subs = {t.description.lower() for t in subs}
    if len(unique_subs) >= 3:
        flags.append({
            "type":    "Multiple Subscriptions",
            "detail":  f"{len(unique_subs)} subscription services detected: "
                       f"{', '.join(list(unique_subs)[:5])}",
            "impact":  round(sum(abs(t.amount) for t in subs), 2),
        })

    # 2. Repeat micro-transactions per month
    micro: dict[tuple, list] = defaultdict(list)
    for t in expenses:
        if abs(t.amount) < 200:
            key = (t.description.lower(), t.date.strftime("%Y-%m"))
            micro[key].append(t)

    for (desc, month), txns in micro.items():
        if len(txns) >= 4:
            flags.append({
                "type":   "Repeat Micro-Transaction",
                "detail": f"'{desc}' charged {len(txns)}x in {month}",
                "impact": round(sum(abs(t.amount) for t in txns), 2),
            })

    return flags
