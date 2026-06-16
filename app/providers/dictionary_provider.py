"""
Dictionary provider — free APIs, no key required.

Priority:
  1. MyMemory (mymemory.translated.net) — word translation, 10K chars/day free
  2. Free Dictionary API (api.dictionaryapi.dev) — English definitions, phonetics
  3. Wiktionary API — multilingual definitions and IPA

Never raises — always returns a result.
"""
from __future__ import annotations
import logging
import httpx

from app.providers.base import BaseProvider, ProviderName, VocabResult, TranslationResult

log = logging.getLogger(__name__)

_TIMEOUT = 5.0

_LANG_FULL = {
    "en": "English", "fr": "French", "de": "German", "es": "Spanish",
    "it": "Italian", "pt": "Portuguese", "ja": "Japanese", "ko": "Korean",
    "zh": "Chinese", "ru": "Russian", "ar": "Arabic", "nl": "Dutch",
}

_WIKT_LANG = {
    "fr": "fr", "de": "de", "es": "es", "it": "it",
    "pt": "pt", "ru": "ru", "nl": "nl", "en": "en",
}


def _mymemory_translate(text: str, src: str, tgt: str) -> str | None:
    """Translate text via MyMemory free API."""
    try:
        r = httpx.get(
            "https://api.mymemory.translated.net/get",
            params={"q": text[:500], "langpair": f"{src}|{tgt}"},
            timeout=_TIMEOUT,
        )
        data = r.json()
        if data.get("responseStatus") == 200:
            translation = data.get("responseData", {}).get("translatedText", "")
            if translation and translation.lower() != text.lower():
                return translation
    except Exception as exc:
        log.debug("MyMemory failed: %s", exc)
    return None


def _free_dict_lookup(word: str) -> dict:
    """Lookup English word via Free Dictionary API."""
    try:
        r = httpx.get(
            f"https://api.dictionaryapi.dev/api/v2/entries/en/{word.lower()}",
            timeout=_TIMEOUT,
        )
        if r.status_code != 200:
            return {}
        data = r.json()
        if not data or not isinstance(data, list):
            return {}
        entry = data[0]
        phonetic = ""
        for ph in entry.get("phonetics", []):
            if ph.get("text"):
                phonetic = ph["text"]
                break
        meanings = entry.get("meanings", [])
        pos, definition, example = "", "", ""
        for m in meanings:
            pos = m.get("partOfSpeech", "").capitalize()
            defs = m.get("definitions", [])
            if defs:
                definition = defs[0].get("definition", "")
                example = defs[0].get("example", "")
            if definition:
                break
        return {
            "phonetic": phonetic,
            "partOfSpeech": pos or "Unknown",
            "definition": definition,
            "example": example,
        }
    except Exception as exc:
        log.debug("FreeDictionary failed for %r: %s", word, exc)
        return {}


def _wiktionary_lookup(word: str, lang_code: str) -> dict:
    """Lookup word via Wiktionary REST API for IPA and definition."""
    try:
        wiki_lang = _WIKT_LANG.get(lang_code, "en")
        r = httpx.get(
            f"https://en.wiktionary.org/api/rest_v1/page/definition/{word.lower()}",
            timeout=_TIMEOUT,
        )
        if r.status_code != 200:
            return {}
        data = r.json()
        # Look for entries in the source language
        entries = data.get(wiki_lang.upper(), data.get("en", []))
        if not entries:
            # Try any available language
            entries = next(iter(data.values()), [])
        if not entries:
            return {}
        first = entries[0]
        pos = first.get("partOfSpeech", "")
        definitions = first.get("definitions", [])
        definition = ""
        example = ""
        if definitions:
            definition = definitions[0].get("definition", "")
            # Strip HTML tags
            import re
            definition = re.sub(r"<[^>]+>", "", definition)
            examples = definitions[0].get("examples", [])
            if examples:
                example = re.sub(r"<[^>]+>", "", examples[0])
        return {
            "partOfSpeech": pos or "Unknown",
            "definition": definition,
            "example": example,
        }
    except Exception as exc:
        log.debug("Wiktionary failed for %r: %s", word, exc)
        return {}


def _mymemory_word(word: str, src: str, tgt: str) -> str:
    """Quick word-level translation via MyMemory."""
    result = _mymemory_translate(word, src, tgt)
    return result or ""


class DictionaryProvider(BaseProvider):
    """
    Purely free, no-key provider using public dictionary APIs.
    Used as a high-quality fallback before OfflineProvider.
    """
    name = ProviderName.DICTIONARY

    def is_available(self) -> bool:
        return True  # always available (pure HTTP, no key needed)

    def enrich_word(
        self, word: str, lemma: str, context: str,
        source_lang: str, target_lang: str,
    ) -> VocabResult:
        w = (lemma or word).lower().strip()

        # Step 1: translate the word
        translation = _mymemory_word(w, source_lang, target_lang)

        # Step 2: get definition data
        if source_lang == "en":
            dict_data = _free_dict_lookup(w)
        else:
            dict_data = _wiktionary_lookup(w, source_lang)
            if not dict_data:
                dict_data = _free_dict_lookup(w)  # English fallback

        phonetic   = dict_data.get("phonetic", "")
        pos        = dict_data.get("partOfSpeech", "Unknown")
        definition = dict_data.get("definition", "")
        example    = dict_data.get("example", "") or context or ""

        return VocabResult(
            word=word,
            lemma=lemma or word,
            translation=translation,
            phonetic=phonetic,
            part_of_speech=pos,
            cefr_level="B1",
            frequency_rank="common",
            example_sentence=example,
            sentence_translation="",
            is_idiom=False,
            is_slang=False,
            explanation=definition,
            provider="dictionary-api",
        )

    def translate_batch(self, blocks, source_lang, target_lang) -> TranslationResult:
        """Translate subtitle blocks via MyMemory."""
        translations = []
        for b in blocks:
            text = b.get("text", "").strip()
            if not text:
                translations.append({"index": b["index"], "text": text})
                continue
            translated = _mymemory_translate(text, source_lang, target_lang) or text
            translations.append({"index": b["index"], "text": translated})
        return TranslationResult(translations=translations, provider="mymemory")
