"""
explainer.py — Chunk 7
Senior-Friendly AI Document Explainer & Jargon Buster.

Supports:
  - Google Gemini (default)
  - OpenAI GPT fallback
  - Mock mode (no API key needed for testing)

Output per document:
  - 5th-grade reading level summary (3 bullets)
  - "Things to Watch Out For" (hidden fees, lock-in periods, exclusions)
  - Regional language translation
"""

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

SUPPORTED_LANGUAGES = {
    "hindi":   "Hindi",
    "tamil":   "Tamil",
    "spanish": "Spanish",
    "french":  "French",
    "bengali": "Bengali",
    "telugu":  "Telugu",
}


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class ExplainerResult:
    summary: list[str]          # 3 simple bullet points
    watch_out: list[str]        # hidden fees, lock-ins, exclusions
    translation: Optional[str]  # full translated summary (if requested)
    language: Optional[str]
    provider: str               # gemini | openai | mock


# ── Prompt builder ────────────────────────────────────────────────────────────

def _build_prompt(text: str, language: Optional[str] = None) -> str:
    lang_instruction = ""
    if language:
        lang_name = SUPPORTED_LANGUAGES.get(language.lower(), language)
        lang_instruction = f"""
4. TRANSLATION:
Translate the 3-bullet summary into {lang_name}. Label it clearly as "Translation ({lang_name}):".
"""
    return f"""You are a financial literacy assistant helping senior citizens understand complex documents.

Analyze the following financial document clause and respond in EXACTLY this format:

SUMMARY:
• [Point 1 — explain in simple words a 10-year-old can understand]
• [Point 2 — explain in simple words a 10-year-old can understand]
• [Point 3 — explain in simple words a 10-year-old can understand]

WATCH OUT FOR:
• [Hidden fee, lock-in period, exclusion, or penalty — be specific]
• [Another risk or trap — be specific]
• [Another risk or trap — be specific]
{lang_instruction}
Document text:
\"\"\"
{text}
\"\"\"
"""


# ── Response parser ───────────────────────────────────────────────────────────

def _parse_response(raw: str, language: Optional[str]) -> tuple[list[str], list[str], Optional[str]]:
    """Parse LLM response into summary bullets, watch-out bullets, and translation."""
    summary, watch_out, translation = [], [], None
    current = None

    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.upper().startswith("SUMMARY"):
            current = "summary"
        elif line.upper().startswith("WATCH OUT"):
            current = "watch_out"
        elif language and line.upper().startswith("TRANSLATION"):
            current = "translation"
            translation = ""
        elif line.startswith("•") or line.startswith("-") or line.startswith("*"):
            content = line.lstrip("•-* ").strip()
            if current == "summary":
                summary.append(content)
            elif current == "watch_out":
                watch_out.append(content)
            elif current == "translation":
                translation = (translation or "") + content + "\n"
        elif current == "translation" and translation is not None:
            translation += line + "\n"

    return summary[:3], watch_out[:3], translation.strip() if translation else None


# ── LLM providers ─────────────────────────────────────────────────────────────

def _call_gemini(prompt: str) -> str:
    import google.generativeai as genai
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(prompt)
    return response.text


def _call_openai(prompt: str) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    return response.choices[0].message.content


def _mock_response(text: str, language: Optional[str]) -> str:
    """Return a deterministic mock response for testing without an API key."""
    lang_block = ""
    if language:
        lang_name = SUPPORTED_LANGUAGES.get(language.lower(), language)
        lang_block = f"\nTranslation ({lang_name}):\n• यह एक परीक्षण अनुवाद है।\n"

    return f"""SUMMARY:
• This document talks about rules for your insurance or loan.
• You may have to pay extra money if you cancel early or miss a payment.
• Always read the fine print before signing anything.

WATCH OUT FOR:
• There may be a lock-in period — you cannot cancel without paying a fee.
• Hidden processing fees may be charged that are not shown upfront.
• Pre-existing conditions or certain situations may not be covered.
{lang_block}"""


# ── Main public function ──────────────────────────────────────────────────────

def explain_document(
    text: str,
    language: Optional[str] = None,
    provider: str = "auto",
) -> ExplainerResult:
    """
    Explain a complex financial document clause in simple language.

    Args:
        text:     The raw financial clause / policy text to explain.
        language: Optional target language for translation
                  (e.g. 'hindi', 'tamil', 'spanish').
        provider: 'gemini' | 'openai' | 'mock' | 'auto'
                  'auto' tries Gemini first, then OpenAI, then mock.

    Returns:
        ExplainerResult with summary, watch_out, translation, and provider used.
    """
    if not text or not text.strip():
        raise ValueError("Document text cannot be empty.")

    prompt = _build_prompt(text.strip(), language)
    used_provider = provider
    raw = ""

    if provider == "mock":
        raw = _mock_response(text, language)
        used_provider = "mock"
    elif provider == "gemini" or (provider == "auto" and GEMINI_API_KEY):
        raw = _call_gemini(prompt)
        used_provider = "gemini"
    elif provider == "openai" or (provider == "auto" and OPENAI_API_KEY):
        raw = _call_openai(prompt)
        used_provider = "openai"
    else:
        # No API keys configured — fall back to mock
        raw = _mock_response(text, language)
        used_provider = "mock"

    summary, watch_out, translation = _parse_response(raw, language)

    # Ensure we always have 3 bullets even if parsing partially fails
    while len(summary) < 3:
        summary.append("Please review the original document for more details.")
    while len(watch_out) < 3:
        watch_out.append("Consult a financial advisor for hidden clauses.")

    return ExplainerResult(
        summary=summary,
        watch_out=watch_out,
        translation=translation,
        language=language,
        provider=used_provider,
    )
