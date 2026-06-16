"""Ollama local model provider — third-tier fallback."""
from __future__ import annotations
import json, httpx
from app.providers.base import BaseProvider, ProviderName, VocabResult, TranslationResult
from app.config import get_settings

_LANG = {
    "en": "English", "fr": "French", "de": "German", "es": "Spanish",
}

_ENRICH_PROMPT = """\
You are a French language expert. Analyse the word "{word}" in context: "{context}"
Return ONLY this JSON (no other text):
{{"translation":"{src} translation","phonetic":"IPA","partOfSpeech":"Noun/Verb/Adjective/Adverb","cefrLevel":"A1/A2/B1/B2/C1","frequencyRank":"common","exampleSentence":"example","sentenceTranslation":"{src} translation","isIdiom":false,"isSlang":false,"explanation":"brief note"}}"""

_TRANSLATE_PROMPT = """\
Translate from {src} to {tgt}. Return ONLY JSON: {{"translations":[{{"index":1,"text":"..."}}]}}
{lines}"""


class OllamaProvider(BaseProvider):
    name = ProviderName.OLLAMA

    def __init__(self):
        self._settings = get_settings()

    def is_available(self) -> bool:
        try:
            r = httpx.get(
                f"{self._settings.ollama_base_url}/api/tags",
                timeout=2.0,
            )
            return r.status_code == 200
        except Exception:
            return False

    def _call(self, prompt: str) -> str:
        r = httpx.post(
            f"{self._settings.ollama_base_url}/api/generate",
            json={
                "model": self._settings.ollama_model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
            },
            timeout=self._settings.ollama_timeout,
        )
        r.raise_for_status()
        return r.json()["response"]

    def enrich_word(self, word, lemma, context, source_lang, target_lang) -> VocabResult:
        src = _LANG.get(source_lang, source_lang)
        tgt = _LANG.get(target_lang, target_lang)
        prompt = _ENRICH_PROMPT.format(
            word=word, context=context or word, src=src, tgt=tgt
        )
        data = json.loads(self._call(prompt))
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
            provider="ollama",
        )

    def translate_batch(self, blocks, source_lang, target_lang) -> TranslationResult:
        src = _LANG.get(source_lang, source_lang)
        tgt = _LANG.get(target_lang, target_lang)
        lines = "\n".join(f"{b['index']}. {b['text']}" for b in blocks)
        prompt = _TRANSLATE_PROMPT.format(src=src, tgt=tgt, lines=lines)
        data = json.loads(self._call(prompt))
        return TranslationResult(
            translations=data.get("translations", []),
            provider="ollama",
        )
