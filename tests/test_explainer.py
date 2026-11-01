import pytest
from unittest.mock import patch
from src.assistant.explainer import (
    explain_document,
    _build_prompt,
    _parse_response,
    _mock_response,
    ExplainerResult,
    SUPPORTED_LANGUAGES,
)

SAMPLE_CLAUSE = """
The insured shall be subject to a mandatory lock-in period of 36 months from the
date of policy commencement. Any surrender or partial withdrawal during this period
shall attract a discontinuance charge of 4% on the fund value or Rs. 6,000,
whichever is lower. Pre-existing conditions diagnosed within 48 months prior to
policy inception are excluded from coverage. The insurer reserves the right to
revise premiums annually based on claims experience, subject to IRDAI approval.
Processing fees of 2% on the sum assured are non-refundable upon cancellation.
"""


# ── _build_prompt() ───────────────────────────────────────────────────────────

class TestBuildPrompt:
    def test_contains_document_text(self):
        prompt = _build_prompt("some clause text")
        assert "some clause text" in prompt

    def test_contains_summary_instruction(self):
        prompt = _build_prompt("text")
        assert "SUMMARY" in prompt.upper()

    def test_contains_watch_out_instruction(self):
        prompt = _build_prompt("text")
        assert "WATCH OUT" in prompt.upper()

    def test_language_instruction_added(self):
        prompt = _build_prompt("text", language="hindi")
        assert "Hindi" in prompt

    def test_no_language_no_translation_block(self):
        prompt = _build_prompt("text", language=None)
        assert "TRANSLATION" not in prompt.upper()


# ── _parse_response() ─────────────────────────────────────────────────────────

class TestParseResponse:
    def test_parses_summary_bullets(self):
        raw = "SUMMARY:\n• Point one\n• Point two\n• Point three\n"
        summary, _, _ = _parse_response(raw, None)
        assert len(summary) == 3
        assert summary[0] == "Point one"

    def test_parses_watch_out_bullets(self):
        raw = "WATCH OUT FOR:\n• Fee one\n• Fee two\n• Fee three\n"
        _, watch_out, _ = _parse_response(raw, None)
        assert len(watch_out) == 3

    def test_parses_translation(self):
        raw = "SUMMARY:\n• A\n• B\n• C\nWATCH OUT FOR:\n• X\nTranslation (Hindi):\n• हिंदी अनुवाद\n"
        _, _, translation = _parse_response(raw, "hindi")
        assert translation is not None
        assert len(translation) > 0

    def test_no_translation_when_not_requested(self):
        raw = "SUMMARY:\n• A\n• B\n• C\nWATCH OUT FOR:\n• X\n"
        _, _, translation = _parse_response(raw, None)
        assert translation is None

    def test_caps_at_three_bullets(self):
        raw = "SUMMARY:\n• A\n• B\n• C\n• D\n• E\n"
        summary, _, _ = _parse_response(raw, None)
        assert len(summary) == 3


# ── explain_document() — mock provider ───────────────────────────────────────

class TestExplainDocumentMock:
    def test_returns_explainer_result(self):
        result = explain_document(SAMPLE_CLAUSE, provider="mock")
        assert isinstance(result, ExplainerResult)

    def test_summary_has_three_bullets(self):
        result = explain_document(SAMPLE_CLAUSE, provider="mock")
        assert len(result.summary) == 3

    def test_watch_out_has_three_bullets(self):
        result = explain_document(SAMPLE_CLAUSE, provider="mock")
        assert len(result.watch_out) == 3

    def test_provider_is_mock(self):
        result = explain_document(SAMPLE_CLAUSE, provider="mock")
        assert result.provider == "mock"

    def test_summary_bullets_are_strings(self):
        result = explain_document(SAMPLE_CLAUSE, provider="mock")
        assert all(isinstance(s, str) and len(s) > 0 for s in result.summary)

    def test_watch_out_bullets_are_strings(self):
        result = explain_document(SAMPLE_CLAUSE, provider="mock")
        assert all(isinstance(w, str) and len(w) > 0 for w in result.watch_out)

    def test_translation_returned_when_language_set(self):
        result = explain_document(SAMPLE_CLAUSE, language="hindi", provider="mock")
        assert result.translation is not None
        assert result.language == "hindi"

    def test_no_translation_when_no_language(self):
        result = explain_document(SAMPLE_CLAUSE, provider="mock")
        assert result.translation is None

    def test_empty_text_raises(self):
        with pytest.raises(ValueError, match="empty"):
            explain_document("   ", provider="mock")

    def test_auto_falls_back_to_mock_without_keys(self):
        with patch("src.assistant.explainer.GEMINI_API_KEY", ""), \
             patch("src.assistant.explainer.OPENAI_API_KEY", ""):
            result = explain_document(SAMPLE_CLAUSE, provider="auto")
        assert result.provider == "mock"


# ── explain_document() — mocked Gemini ───────────────────────────────────────

class TestExplainDocumentGemini:
    FAKE_RESPONSE = """SUMMARY:
• This policy locks your money for 3 years.
• You will be charged a fee if you cancel early.
• Some health conditions from before are not covered.

WATCH OUT FOR:
• A 4% fee is charged if you withdraw money early.
• Pre-existing conditions are excluded for 4 years.
• Premiums can go up every year without your approval."""

    def test_gemini_provider_used(self):
        with patch("src.assistant.explainer.GEMINI_API_KEY", "fake-key"), \
             patch("src.assistant.explainer._call_gemini", return_value=self.FAKE_RESPONSE):
            result = explain_document(SAMPLE_CLAUSE, provider="gemini")
        assert result.provider == "gemini"
        assert len(result.summary) == 3
        assert len(result.watch_out) == 3

    def test_gemini_summary_content(self):
        with patch("src.assistant.explainer.GEMINI_API_KEY", "fake-key"), \
             patch("src.assistant.explainer._call_gemini", return_value=self.FAKE_RESPONSE):
            result = explain_document(SAMPLE_CLAUSE, provider="gemini")
        assert "3 years" in result.summary[0]

    def test_gemini_watch_out_content(self):
        with patch("src.assistant.explainer.GEMINI_API_KEY", "fake-key"), \
             patch("src.assistant.explainer._call_gemini", return_value=self.FAKE_RESPONSE):
            result = explain_document(SAMPLE_CLAUSE, provider="gemini")
        assert any("fee" in w.lower() or "excluded" in w.lower() for w in result.watch_out)


# ── Supported languages ───────────────────────────────────────────────────────

class TestSupportedLanguages:
    def test_hindi_supported(self):
        assert "hindi" in SUPPORTED_LANGUAGES

    def test_tamil_supported(self):
        assert "tamil" in SUPPORTED_LANGUAGES

    def test_spanish_supported(self):
        assert "spanish" in SUPPORTED_LANGUAGES

    def test_all_values_are_strings(self):
        assert all(isinstance(v, str) for v in SUPPORTED_LANGUAGES.values())
