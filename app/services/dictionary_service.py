"""
Free Dictionary API — https://api.dictionaryapi.dev
No API key required. English words only.

Used as last-resort enrichment fallback when Gemini and Groq are both unavailable.
"""
from __future__ import annotations
import httpx

_BASE = "https://api.dictionaryapi.dev/api/v2/entries"

_POS_MAP = {
    "noun": "Noun", "verb": "Verb", "adjective": "Adjective",
    "adverb": "Adverb", "pronoun": "Noun", "interjection": "Idiom",
    "phrase": "Phrase",
}


def get_word_info(word: str, lang: str = "en") -> dict | None:
    """
    Fetch phonetics, definition, and example for a word.
    Returns None if word not found or lang is not English.
    """
    if lang != "en":
        return None
    try:
        with httpx.Client(timeout=5.0) as client:
            r = client.get(f"{_BASE}/{lang}/{word.lower()}")
            if r.status_code != 200:
                return None
            data = r.json()
            if not data or not isinstance(data, list):
                return None

            entry = data[0]
            phonetic = entry.get("phonetic", "")
            if not phonetic:
                for ph in entry.get("phonetics", []):
                    if ph.get("text"):
                        phonetic = ph["text"]
                        break

            definition = ""
            example = ""
            pos = "Noun"
            for meaning in entry.get("meanings", []):
                raw_pos = meaning.get("partOfSpeech", "noun")
                pos = _POS_MAP.get(raw_pos, "Noun")
                for defn in meaning.get("definitions", []):
                    if defn.get("definition"):
                        definition = defn["definition"]
                        example = defn.get("example", "")
                        break
                if definition:
                    break

            return {
                "phonetic":    phonetic,
                "pos":         pos,
                "explanation": definition,
                "example":     example,
                "audio_url":   _get_audio_url(entry),
            }
    except Exception:
        return None


def _get_audio_url(entry: dict) -> str:
    for ph in entry.get("phonetics", []):
        if ph.get("audio"):
            url = ph["audio"]
            return url if url.startswith("http") else f"https:{url}"
    return ""


def enrich_word_minimal(
    word: str,
    context: str,
    source_lang: str,
    target_lang: str,
) -> dict:
    """
    Build an enrichment dict from the Dictionary API.
    Falls back gracefully if word not found or not English.
    """
    info = get_word_info(word, target_lang) if target_lang == "en" else None
    return {
        "translation":          "",
        "pos":                  info["pos"]         if info else "",   # empty → caller keeps spaCy POS
        "phonetic":             info["phonetic"]    if info else "",
        "explanation":          info["explanation"] if info else "",
        "sentence_translation": context,
        "example":              info.get("example", "") if info else "",
        "audio_url":            info.get("audio_url", "") if info else "",
    }
