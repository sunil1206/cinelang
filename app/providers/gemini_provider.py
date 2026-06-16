"""Gemini 2.5 Flash provider — PRIMARY AI provider."""
from __future__ import annotations
import json
import re
import httpx
from app.providers.base import BaseProvider, ProviderName, VocabResult, TranslationResult
from app.config import get_settings

_LANG = {
    "en": "English", "fr": "French", "de": "German", "es": "Spanish",
    "it": "Italian", "pt": "Portuguese", "ja": "Japanese", "ko": "Korean",
    "zh": "Mandarin", "ru": "Russian", "ar": "Arabic", "nl": "Dutch",
}

_ENRICH_PROMPT = """\
You are a language expert. Analyse the {tgt} word: "{word}" (lemma: "{lemma}")
Context sentence: "{context}"

Return ONLY a valid JSON object with exactly these keys:
{{
  "translation": "{src} translation of the word",
  "phonetic": "IPA pronunciation e.g. /bɔ̃ʒuʁ/",
  "partOfSpeech": "one of: Noun Verb Adjective Adverb Idiom Phrase Slang",
  "cefrLevel": "one of: A1 A2 B1 B2 C1",
  "frequencyRank": "one of: very common common uncommon rare",
  "exampleSentence": "natural {tgt} example sentence using this word",
  "sentenceTranslation": "{src} translation of that example sentence",
  "isIdiom": false,
  "isSlang": false,
  "explanation": "1-2 sentence cultural or usage note"
}}"""

_TRANSLATE_PROMPT = """\
Translate the following {src} subtitle lines to {tgt}.
Return ONLY valid JSON with this structure: {{"translations": [{{"index": 1, "text": "translated text"}}]}}

Subtitle lines:
{lines}"""


class GeminiProvider(BaseProvider):
    name = ProviderName.GEMINI
    _BASE = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(self):
        self._settings = get_settings()

    def is_available(self) -> bool:
        key = self._settings.gemini_api_key
        return bool(key and len(key) > 10)

    def _call(self, prompt: str, max_tokens: int = 1024) -> str:
        model = self._settings.gemini_model
        url   = f"{self._BASE}/{model}:generateContent"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": max_tokens,
                "responseMimeType": "application/json",
            },
        }
        r = httpx.post(
            url,
            json=payload,
            params={"key": self._settings.gemini_api_key},
            timeout=self._settings.gemini_timeout,
        )
        if r.status_code in (400, 401, 403):
            raise RuntimeError(f"Gemini rejected ({r.status_code}): {r.text[:200]}")
        r.raise_for_status()

        data = r.json()
        # Extract text from response
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            raise RuntimeError(f"Unexpected Gemini response shape: {str(data)[:200]}")

        # Strip markdown fences if any
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if len(lines) > 2 else text

        # Extract JSON object if surrounded by extra text
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            text = match.group(0)

        return text

    def enrich_word(self, word, lemma, context, source_lang, target_lang) -> VocabResult:
        src    = _LANG.get(source_lang, source_lang)
        tgt    = _LANG.get(target_lang, target_lang)
        prompt = _ENRICH_PROMPT.format(
            word=word, lemma=lemma or word,
            context=context or word,
            src=src, tgt=tgt,
        )
        raw  = self._call(prompt, max_tokens=512)
        data = json.loads(raw)
        return VocabResult(
            word=word, lemma=lemma or word,
            translation=data.get("translation", ""),
            phonetic=data.get("phonetic", ""),
            part_of_speech=data.get("partOfSpeech", "Noun"),
            cefr_level=data.get("cefrLevel", "B1"),
            frequency_rank=data.get("frequencyRank", "common"),
            example_sentence=data.get("exampleSentence", ""),
            sentence_translation=data.get("sentenceTranslation", ""),
            is_idiom=bool(data.get("isIdiom", False)),
            is_slang=bool(data.get("isSlang", False)),
            explanation=data.get("explanation", ""),
            provider="gemini-2.5-flash",
        )

    def translate_batch(self, blocks, source_lang, target_lang) -> TranslationResult:
        src   = _LANG.get(source_lang, source_lang)
        tgt   = _LANG.get(target_lang, target_lang)
        lines = "\n".join(f"{b['index']}. {b['text']}" for b in blocks)
        prompt = _TRANSLATE_PROMPT.format(src=src, tgt=tgt, lines=lines)
        raw    = self._call(prompt, max_tokens=2048)

        # Handle both {translations:[]} and [{index, text}] shapes
        data = json.loads(raw)
        if isinstance(data, list):
            translations = data
        else:
            translations = data.get("translations", [])

        return TranslationResult(translations=translations, provider="gemini-2.5-flash")
