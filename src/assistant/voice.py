"""
voice.py — Chunk 8
Speech-to-Text (STT) and Text-to-Speech (TTS) for FinGuard AI.

STT : SpeechRecognition (Google Web Speech API — free, no key needed)
TTS : gTTS (Google Text-to-Speech) → MP3 → base64 → browser <audio> autoplay
"""

from __future__ import annotations

import base64
import io
import tempfile
from typing import Optional

# ── TTS ───────────────────────────────────────────────────────────────────────
try:
    from gtts import gTTS
    _GTTS_AVAILABLE = True
except ImportError:
    _GTTS_AVAILABLE = False

# ── STT ───────────────────────────────────────────────────────────────────────
try:
    import speech_recognition as sr
    _SR_AVAILABLE = True
except ImportError:
    _SR_AVAILABLE = False


# ── TTS Functions ─────────────────────────────────────────────────────────────

def text_to_speech_bytes(text: str, lang: str = "en") -> Optional[bytes]:
    """
    Convert text to MP3 audio bytes using gTTS.

    Parameters
    ----------
    text : the text to speak
    lang : BCP-47 language code (default 'en')

    Returns
    -------
    MP3 bytes, or None if gTTS is not installed.
    """
    if not _GTTS_AVAILABLE:
        return None
    if not text or not text.strip():
        return None

    buf = io.BytesIO()
    gTTS(text=text.strip(), lang=lang, slow=False).write_to_fp(buf)
    buf.seek(0)
    return buf.read()


def text_to_speech_html(text: str, lang: str = "en") -> Optional[str]:
    """
    Return an HTML <audio> tag with autoplay that speaks the given text.
    Embed the MP3 as a base64 data URI so no file is written to disk.

    Returns None if gTTS is unavailable.
    """
    mp3_bytes = text_to_speech_bytes(text, lang=lang)
    if mp3_bytes is None:
        return None
    b64 = base64.b64encode(mp3_bytes).decode("utf-8")
    return (
        f'<audio autoplay style="display:none">'
        f'<source src="data:audio/mp3;base64,{b64}" type="audio/mp3">'
        f"</audio>"
    )


def build_report_speech(
    income: float,
    expenses: float,
    balance: float,
    health_score: int,
    ef_pct: float,
    next_emi_name: Optional[str] = None,
    next_emi_days: Optional[int] = None,
    currency: str = "rupees",
) -> str:
    """
    Build a natural-language summary string suitable for TTS playback.
    Keeps numbers rounded and sentences short for clarity.
    """
    lines = [
        "Hello! Here is your FinGuard financial summary.",
        f"Your total income is {int(income):,} {currency}.",
        f"Your total expenses are {int(expenses):,} {currency}.",
        f"Your remaining balance is {int(balance):,} {currency}.",
        f"Your financial health score is {health_score} out of 100.",
        f"Your emergency fund is {ef_pct:.0f} percent complete.",
    ]
    if next_emi_name and next_emi_days is not None:
        if next_emi_days == 0:
            lines.append(f"Warning! Your {next_emi_name} EMI is due today.")
        elif next_emi_days <= 5:
            lines.append(
                f"Alert! Your {next_emi_name} EMI is due in {next_emi_days} days. "
                "Please ensure your account has sufficient balance."
            )
        else:
            lines.append(f"Your next EMI, {next_emi_name}, is due in {next_emi_days} days.")
    lines.append("Stay financially healthy. Goodbye!")
    return " ".join(lines)


# ── STT Functions ─────────────────────────────────────────────────────────────

def speech_to_text_from_file(audio_file_path: str, language: str = "en-IN") -> str:
    """
    Transcribe speech from a WAV/AIFF/FLAC audio file using Google Web Speech API.

    Parameters
    ----------
    audio_file_path : path to the audio file
    language        : BCP-47 language code (default 'en-IN' for Indian English)

    Returns
    -------
    Transcribed text string, or an error message string.
    """
    if not _SR_AVAILABLE:
        return "SpeechRecognition library not installed. Run: pip install SpeechRecognition"

    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(audio_file_path) as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.3)
            audio = recognizer.record(source)
        return recognizer.recognize_google(audio, language=language)
    except sr.UnknownValueError:
        return "Could not understand the audio. Please speak clearly and try again."
    except sr.RequestError as e:
        return f"Speech recognition service error: {e}"
    except Exception as e:
        return f"Error processing audio: {e}"


def speech_to_text_from_bytes(audio_bytes: bytes, language: str = "en-IN") -> str:
    """
    Transcribe speech from raw audio bytes (WAV format).
    Writes to a temp file internally, then calls speech_to_text_from_file.
    """
    if not _SR_AVAILABLE:
        return "SpeechRecognition library not installed."

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    return speech_to_text_from_file(tmp_path, language=language)


def parse_voice_command(text: str) -> dict:
    """
    Parse a transcribed voice command into a structured intent dict.

    Supported intents:
      - read_report   : "read my report", "read aloud", "speak summary"
      - show_score    : "show my score", "health score", "risk score"
      - show_emi      : "show EMI", "upcoming bills", "next payment"
      - show_fund     : "emergency fund", "savings target"
      - help          : "help", "what can you do"
      - unknown       : anything else

    Returns
    -------
    {"intent": str, "raw": str}
    """
    lower = text.lower().strip()

    if any(kw in lower for kw in ["read", "speak", "aloud", "summary", "report"]):
        return {"intent": "read_report", "raw": text}
    if any(kw in lower for kw in ["score", "health", "risk"]):
        return {"intent": "show_score", "raw": text}
    if any(kw in lower for kw in ["emi", "bill", "payment", "due"]):
        return {"intent": "show_emi", "raw": text}
    if any(kw in lower for kw in ["emergency", "fund", "savings", "corpus"]):
        return {"intent": "show_fund", "raw": text}
    if any(kw in lower for kw in ["help", "what can", "how to"]):
        return {"intent": "help", "raw": text}

    return {"intent": "unknown", "raw": text}


# ── Availability Checks ───────────────────────────────────────────────────────

def tts_available() -> bool:
    return _GTTS_AVAILABLE


def stt_available() -> bool:
    return _SR_AVAILABLE
