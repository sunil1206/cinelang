"""Gemini 2.5 Flash — structured JSON generation with exponential back-off."""
import json
import time
from typing import Any

import httpx

from app.config import get_settings
from app.core.exceptions import ServiceUnavailableError

settings = get_settings()

_LANG_NAMES = {
    "en": "English",  "fr": "French",   "de": "German",   "es": "Spanish",
    "it": "Italian",  "pt": "Portuguese","ja": "Japanese", "ko": "Korean",
    "zh": "Mandarin", "ru": "Russian",   "ar": "Arabic",   "nl": "Dutch",
    "pl": "Polish",   "sv": "Swedish",   "tr": "Turkish",  "hi": "Hindi",
}

# ── JSON schemas passed to Gemini responseSchema ──────────────────────────────

_POS_ENUM = ["Noun", "Verb", "Adjective", "Adverb", "Idiom", "Slang", "Phrase"]

ENRICH_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "translation":         {"type": "STRING"},
        "pos":                 {"type": "STRING", "enum": _POS_ENUM},
        "phonetic":            {"type": "STRING"},
        "explanation":         {"type": "STRING"},
        "sentence_translation": {"type": "STRING"},
    },
    "required": ["translation", "pos", "phonetic", "explanation", "sentence_translation"],
}

TRANSLATE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "translations": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "index": {"type": "INTEGER"},
                    "text":  {"type": "STRING"},
                },
                "required": ["index", "text"],
            },
        },
        "vocabulary": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "word":        {"type": "STRING"},
                    "translation": {"type": "STRING"},
                    "pos":         {"type": "STRING", "enum": _POS_ENUM},
                    "phonetic":    {"type": "STRING"},
                    "explanation": {"type": "STRING"},
                    "example":     {"type": "STRING"},
                },
                "required": ["word", "translation", "pos", "phonetic", "explanation", "example"],
            },
        },
    },
    "required": ["translations", "vocabulary"],
}

DETECT_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "code":       {"type": "STRING"},
        "name":       {"type": "STRING"},
        "confidence": {"type": "NUMBER"},
    },
    "required": ["code", "name", "confidence"],
}


# ── Low-level HTTP call with retry ────────────────────────────────────────────

def _gemini_url() -> str:
    return (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.gemini_model}:generateContent?key={settings.gemini_api_key}"
    )


def _no_key() -> bool:
    return not settings.gemini_api_key


def _call(payload: dict, retries: int = 3) -> dict:
    if _no_key():
        raise ServiceUnavailableError("GEMINI_API_KEY not configured")

    last_exc: Exception = RuntimeError("No attempts made")
    for attempt, delay in enumerate([2, 5, 10][:retries]):
        try:
            with httpx.Client(timeout=60.0) as client:
                r = client.post(_gemini_url(), json=payload)
                if r.status_code in (400, 401, 403):
                    raise ServiceUnavailableError(f"Gemini API key rejected ({r.status_code})")
                if r.status_code == 429:
                    # Rate limited — wait longer before retry
                    if attempt < retries - 1:
                        time.sleep(delay * 3)
                    last_exc = Exception(f"Rate limited (429)")
                    continue
                r.raise_for_status()
                return r.json()
        except Exception as exc:
            last_exc = exc
            if attempt < retries - 1:
                time.sleep(delay)

    raise ServiceUnavailableError(f"Gemini API unavailable: {last_exc}")


def _call_json(payload: dict) -> Any:
    data = _call(payload)
    raw = data["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(raw)


# ── Public API ────────────────────────────────────────────────────────────────

def detect_language(sample_text: str) -> dict:
    """Return {'code': 'fr', 'name': 'French', 'confidence': 0.99}."""
    if _no_key():
        return {"code": "en", "name": "English", "confidence": 0.5}
    return _call_json({
        "contents": [{"parts": [{"text": f"Detect language:\n\n{sample_text[:600]}"}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema":   DETECT_SCHEMA,
            "temperature":      0,
        },
    })


def enrich_word(word: str, sentence: str, source_lang: str, target_lang: str) -> dict:
    """Return enrichment dict matching ENRICH_SCHEMA."""
    if _no_key():
        return {
            "translation": word,
            "pos": "Noun",
            "phonetic": "",
            "explanation": "Gemini API key not configured — add GEMINI_API_KEY to .env for AI enrichment.",
            "sentence_translation": sentence,
        }
    sn = _LANG_NAMES.get(source_lang, source_lang)
    tn = _LANG_NAMES.get(target_lang, target_lang)
    prompt = (
        f"Analyse this {tn} word: '{word}'\n"
        f"Context sentence: \"{sentence}\"\n"
        f"Provide accurate {sn} translation, part of speech, IPA-style phonetic guide, "
        f"a short usage/cultural explanation, and a fluent {sn} translation of the context sentence."
    )
    return _call_json({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema":   ENRICH_SCHEMA,
            "temperature":      0.2,
        },
    })


def translate_batch(blocks: list[dict], source_lang: str, target_lang: str) -> dict:
    """Translate up to 25 subtitle blocks and extract vocabulary.

    blocks: [{"index": int, "text": str}, ...]
    Returns dict matching TRANSLATE_SCHEMA.
    """
    if _no_key():
        raise ServiceUnavailableError("GEMINI_API_KEY not configured")
    sn = _LANG_NAMES.get(source_lang, source_lang)
    tn = _LANG_NAMES.get(target_lang, target_lang)
    numbered = "\n".join(f"{b['index']}. {b['text']}" for b in blocks)
    prompt = (
        f"Translate these {sn} subtitles into {tn}.\n"
        f"Also extract 5-8 vocabulary items from the {tn} translations that a learner should know "
        f"(idioms, expressive verbs, culturally interesting words, slang).\n\n"
        f"Subtitles:\n{numbered}"
    )
    return _call_json({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema":   TRANSLATE_SCHEMA,
            "temperature":      0.3,
        },
    })
