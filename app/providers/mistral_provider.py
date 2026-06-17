"""Mistral AI provider — Mistral Nemo / Small (primary, best French quality)."""
from __future__ import annotations
import json
import re
from app.providers.base import BaseProvider, ProviderName, VocabResult, TranslationResult
from app.config import get_settings

_LANG = {
    "en": "English", "fr": "French", "de": "German", "es": "Spanish",
    "it": "Italian", "pt": "Portuguese", "ja": "Japanese", "ko": "Korean",
    "zh": "Mandarin", "ru": "Russian", "ar": "Arabic", "nl": "Dutch",
}

_ENRICH_PROMPT = """\
You are a linguistics expert specialising in {tgt}.
Analyse the {tgt} word: "{word}" (lemma: "{lemma}")
Context sentence: "{context}"

Return ONLY a valid JSON object with these exact keys:
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
Translate these {src} subtitle lines to {tgt}.
Return ONLY valid JSON: {{"translations": [{{"index": 1, "text": "translated text"}}]}}

Lines:
{lines}"""


class MistralProvider(BaseProvider):
    name = ProviderName.MISTRAL

    def __init__(self):
        self._settings = get_settings()
        self._client = None

    def _get_client(self):
        if not self._client:
            from mistralai import Mistral
            self._client = Mistral(api_key=self._settings.mistral_api_key)
        return self._client

    def is_available(self) -> bool:
        return bool(self._settings.mistral_api_key and len(self._settings.mistral_api_key) > 10)

    def _parse_json(self, text: str) -> dict:
        text = text.strip()
        # Strip markdown fences
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        match = re.search(r'\{.*\}', text, re.DOTALL)
        return json.loads(match.group(0) if match else text)

    def enrich_word(self, word, lemma, context, source_lang, target_lang) -> VocabResult:
        client = self._get_client()
        src = _LANG.get(source_lang, source_lang)
        tgt = _LANG.get(target_lang, target_lang)
        prompt = _ENRICH_PROMPT.format(
            word=word, lemma=lemma or word, context=context or word, src=src, tgt=tgt
        )
        resp = client.chat.complete(
            model=self._settings.mistral_model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=512,
            temperature=0.1,
        )
        data = self._parse_json(resp.choices[0].message.content)
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
            provider=f"mistral/{self._settings.mistral_model}",
        )

    def translate_batch(self, blocks, source_lang, target_lang) -> TranslationResult:
        client = self._get_client()
        src = _LANG.get(source_lang, source_lang)
        tgt = _LANG.get(target_lang, target_lang)
        lines = "\n".join(f"{b['index']}. {b['text']}" for b in blocks)
        resp = client.chat.complete(
            model=self._settings.mistral_model,
            messages=[{"role": "user", "content": _TRANSLATE_PROMPT.format(src=src, tgt=tgt, lines=lines)}],
            response_format={"type": "json_object"},
            max_tokens=2048,
            temperature=0.0,
        )
        data = self._parse_json(resp.choices[0].message.content)
        translations = data if isinstance(data, list) else data.get("translations", [])
        return TranslationResult(translations=translations, provider=f"mistral/{self._settings.mistral_model}")
