"""Groq provider — Llama 3.3 70B. Primary AI provider."""
from __future__ import annotations
import json
from app.providers.base import BaseProvider, ProviderName, VocabResult, TranslationResult
from app.config import get_settings

_LANG = {
    "en": "English", "fr": "French", "de": "German", "es": "Spanish",
    "it": "Italian", "pt": "Portuguese", "ja": "Japanese", "ko": "Korean",
    "zh": "Mandarin", "ru": "Russian", "ar": "Arabic", "nl": "Dutch",
}

_ENRICH_PROMPT = """\
Analyse the {tgt} word: "{word}" (lemma: "{lemma}")
Context: "{context}"

Return ONLY a JSON object with these exact keys:
{{
  "translation": "{src} translation of the word",
  "phonetic": "IPA pronunciation e.g. /bɔ̃ʒuʁ/",
  "partOfSpeech": "one of: Noun Verb Adjective Adverb Idiom Phrase Slang",
  "cefrLevel": "one of: A1 A2 B1 B2 C1",
  "frequencyRank": "one of: very common common uncommon rare",
  "exampleSentence": "natural {tgt} example sentence using the word",
  "sentenceTranslation": "{src} translation of the example sentence",
  "isIdiom": false,
  "isSlang": false,
  "explanation": "short cultural/usage note (1-2 sentences)"
}}"""

_TRANSLATE_PROMPT = """\
Translate these {src} subtitles to {tgt}.
Return ONLY JSON: {{"translations": [{{"index": 1, "text": "..."}}]}}

Subtitles:
{lines}"""


class GroqProvider(BaseProvider):
    name = ProviderName.GROQ

    def __init__(self):
        self._settings = get_settings()
        self._client = None

    def _get_client(self):
        if not self._client:
            from groq import Groq
            self._client = Groq(api_key=self._settings.groq_api_key)
        return self._client

    def is_available(self) -> bool:
        return bool(self._settings.groq_api_key)

    def enrich_word(self, word, lemma, context, source_lang, target_lang) -> VocabResult:
        client = self._get_client()
        src = _LANG.get(source_lang, source_lang)
        tgt = _LANG.get(target_lang, target_lang)
        prompt = _ENRICH_PROMPT.format(
            word=word, lemma=lemma, context=context or word, src=src, tgt=tgt
        )
        resp = client.chat.completions.create(
            model=self._settings.groq_model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=512,
            temperature=0.1,
            timeout=self._settings.groq_timeout,
        )
        data = json.loads(resp.choices[0].message.content)
        return VocabResult(
            word=word, lemma=lemma,
            translation=data.get("translation", ""),
            phonetic=data.get("phonetic", ""),
            part_of_speech=data.get("partOfSpeech", "Noun"),
            cefr_level=data.get("cefrLevel", "B1"),
            frequency_rank=data.get("frequencyRank", "common"),
            example_sentence=data.get("exampleSentence", ""),
            sentence_translation=data.get("sentenceTranslation", ""),
            is_idiom=data.get("isIdiom", False),
            is_slang=data.get("isSlang", False),
            explanation=data.get("explanation", ""),
            provider="groq",
        )

    def translate_batch(self, blocks, source_lang, target_lang) -> TranslationResult:
        client = self._get_client()
        src = _LANG.get(source_lang, source_lang)
        tgt = _LANG.get(target_lang, target_lang)
        lines = "\n".join(f"{b['index']}. {b['text']}" for b in blocks)
        prompt = _TRANSLATE_PROMPT.format(src=src, tgt=tgt, lines=lines)
        resp = client.chat.completions.create(
            model=self._settings.groq_model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=2048,
            temperature=0.0,
            timeout=self._settings.groq_timeout,
        )
        data = json.loads(resp.choices[0].message.content)
        return TranslationResult(
            translations=data.get("translations", []),
            provider="groq",
        )
