"""Offline provider — local dictionary + Google Translate fallback. Never fails."""
from __future__ import annotations
import logging
from app.providers.base import BaseProvider, ProviderName, VocabResult, TranslationResult
from app.offline.dictionary import lookup_with_fallback

log = logging.getLogger(__name__)


def _google_translate_word(word: str, source_lang: str, target_lang: str) -> str:
    """Single-word translation via deep-translator. Returns empty string on failure."""
    try:
        from deep_translator import GoogleTranslator
        result = GoogleTranslator(source=source_lang, target=target_lang).translate(word)
        return result or ""
    except Exception as exc:
        log.debug("Google word translate failed for %r: %s", word, exc)
        return ""


class OfflineProvider(BaseProvider):
    name = ProviderName.OFFLINE

    def is_available(self) -> bool:
        return True

    def enrich_word(self, word, lemma, context, source_lang, target_lang) -> VocabResult:
        # 1. Check local dictionary first (has rich data for common French words)
        data = lookup_with_fallback(word, lemma)

        # 2. If no translation found locally, try Google Translate for the word
        translation = data.get("translation", "")
        if not translation:
            translation = _google_translate_word(word, source_lang, target_lang)

        return VocabResult(
            word=word,
            lemma=lemma or word,
            translation=translation,
            phonetic=data.get("phonetic", ""),
            part_of_speech=data.get("partOfSpeech", "Unknown"),
            cefr_level=data.get("cefrLevel", "B1"),
            frequency_rank=data.get("frequencyRank", "common"),
            example_sentence=data.get("exampleSentence", ""),
            sentence_translation=data.get("sentenceTranslation", ""),
            is_idiom=data.get("isIdiom", False),
            is_slang=data.get("isSlang", False),
            explanation=data.get("explanation", ""),
            provider="offline+google",
        )

    def translate_batch(self, blocks, source_lang, target_lang) -> TranslationResult:
        return TranslationResult(
            translations=[{"index": b["index"], "text": b["text"]} for b in blocks],
            provider="offline",
        )
