"""
prompts.py — AI system instructions and prompt templates for Financial Friend AI.
Keeps all prompt logic separate from response generation.
"""

from __future__ import annotations

SYSTEM_PROMPT = """
You are Financial Friend AI, a personal financial advisor embedded in the FinGuard AI dashboard.
You have access to the user's actual transaction data.

Rules:
- Only use figures from the provided financial context. Never invent numbers.
- Be concise, friendly and actionable.
- Use Indian Rupee (₹) for all amounts.
- Always suggest the relevant dashboard tab for deeper analysis.
- If data is missing, say so clearly and ask the user to upload their CSV.
"""

INTENT_KEYWORDS: dict[str, list[str]] = {
    "reduce_expenses":  ["reduce", "cut", "lower", "less", "save", "saving", "savings"],
    "spending_breakdown": ["spending", "spend", "most", "category", "categories", "where", "breakdown"],
    "health_score":     ["health", "score", "risk", "rating", "financial health"],
    "emergency_fund":   ["emergency", "fund", "corpus", "maintain", "safety", "need"],
    "emi_bills":        ["emi", "bill", "payment", "upcoming", "due", "loan", "recurring"],
    "income":           ["income", "earn", "salary", "revenue"],
    "balance":          ["balance", "left", "remaining", "net", "how much"],
    "budget":           ["budget", "overspend", "over budget", "limit"],
}


def detect_intent(question: str) -> str:
    """Return the best-matching intent key for a user question."""
    q = question.lower().strip()
    for intent, keywords in INTENT_KEYWORDS.items():
        if any(kw in q for kw in keywords):
            return intent
    return "fallback"


FALLBACK_RESPONSE = (
    "🤔 I'm not sure about that. Here are things I can help with:\n\n"
    "- 💡 How can I reduce my monthly expenses?\n"
    "- 📊 Where am I spending the most?\n"
    "- 🏆 What is my financial health score?\n"
    "- 🛡️ How much emergency fund do I need?\n"
    "- 💳 Which EMI payments are upcoming?"
)

NO_DATA_RESPONSE = (
    "📂 I don't have your financial data yet. "
    "Please upload your transactions CSV in the Dashboard to get personalised answers!"
)
