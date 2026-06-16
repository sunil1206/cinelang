"""
CEFR classification using wordfreq Zipf scores.

Zipf scale reference:
  7.0  → "the" (most common English word)
  6.5  → very common everyday words
  5.5  → frequent words learners meet early
  4.5  → words requiring deliberate study
  3.5  → less common, B2/C1 territory
  2.0  → rare / technical / archaic
"""
from __future__ import annotations
from functools import lru_cache

# Supported language codes → wordfreq language codes
_LANG_MAP = {
    "fr": "fr", "de": "de", "es": "es", "it": "it",
    "pt": "pt", "nl": "nl", "pl": "pl", "ru": "ru",
    "ja": "ja", "ko": "ko", "zh": "zh", "ar": "ar",
    "en": "en", "sv": "sv", "tr": "tr", "hi": "hi",
}

# Zipf thresholds for CEFR bands (tuned against common CEFR word lists)
_THRESHOLDS = [
    (6.0, "A1"),
    (5.0, "A2"),
    (4.0, "B1"),
    (3.0, "B2"),
    (0.0, "C1"),
]


def classify(word: str, lang_code: str) -> tuple[str, float]:
    """
    Returns (cefr_level, zipf_score) for a word in a given language.
    Falls back to B1/0.0 if the language is not supported by wordfreq.
    """
    wf_lang = _LANG_MAP.get(lang_code, lang_code)
    try:
        from wordfreq import zipf_frequency
        zipf = zipf_frequency(word.lower(), wf_lang)
    except Exception:
        return "B1", 0.0

    for threshold, level in _THRESHOLDS:
        if zipf >= threshold:
            return level, round(zipf, 2)
    return "C1", round(zipf, 2)


def classify_batch(words: list[str], lang_code: str) -> dict[str, tuple[str, float]]:
    """Classify a list of words. Returns {word: (cefr, zipf)}."""
    return {w: classify(w, lang_code) for w in words}


def cefr_rank(level: str) -> int:
    """Numeric rank for sorting — lower is easier."""
    return {"A1": 1, "A2": 2, "B1": 3, "B2": 4, "C1": 5}.get(level, 3)
