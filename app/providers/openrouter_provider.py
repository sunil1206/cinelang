"""OpenRouter provider — free LLM models, OpenAI-compatible API."""
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
Context: "{context}"

Return ONLY a valid JSON object with exactly these keys:
{{
  "translation": "{src} translation",
  "phonetic": "IPA e.g. /bɔ̃ʒuʁ/",
  "partOfSpeech": "Noun|Verb|Adjective|Adverb|Idiom|Phrase|Slang",
  "cefrLevel": "A1|A2|B1|B2|C1",
  "frequencyRank": "very common|common|uncommon|rare",
  "exampleSentence": "natural {tgt} example sentence",
  "sentenceTranslation": "{src} translation of that sentence",
  "isIdiom": false,
  "isSlang": false,
  "explanation": "1-2 sentence usage note"
}}"""

_TRANSLATE_PROMPT = """\
Translate the following {src} subtitle lines to {tgt}.
Return ONLY valid JSON: {{"translations": [{{"index": 1, "text": "translated"}}]}}

Lines:
{lines}"""

_FREE_MODEL  = "mistralai/mistral-nemo"          # near-zero cost, best French quality
_FALLBACK_MODEL = "meta-llama/llama-3.3-70b-instruct:free"  # free fallback
_BASE_URL   = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterProvider(BaseProvider):
    name = ProviderName.OPENROUTER

    def __init__(self):
        self._settings = get_settings()

    def is_available(self) -> bool:
        key = self._settings.openrouter_api_key
        return bool(key and len(key) > 10)

    def _call(self, prompt: str, max_tokens: int = 1024, model: str = _FREE_MODEL) -> str:
        r = httpx.post(
            _BASE_URL,
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": 0.1,
            },
            headers={
                "Authorization": f"Bearer {self._settings.openrouter_api_key}",
                "HTTP-Referer": "https://cinelang.app",
                "X-Title": "CineLang",
            },
            timeout=25,
        )
        if r.status_code == 429 and model == _FREE_MODEL:
            # Rate-limited on primary — retry with free fallback
            return self._call(prompt, max_tokens, model=_FALLBACK_MODEL)
        if r.status_code in (400, 401, 403):
            raise RuntimeError(f"OpenRouter rejected ({r.status_code}): {r.text[:200]}")
        r.raise_for_status()

        text = r.json()["choices"][0]["message"]["content"].strip()

        # Strip markdown fences
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if len(lines) > 2 else text

        # Extract JSON
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            text = match.group(0)
        return text

    def enrich_word(self, word, lemma, context, source_lang, target_lang) -> VocabResult:
        src = _LANG.get(source_lang, source_lang)
        tgt = _LANG.get(target_lang, target_lang)
        raw  = self._call(_ENRICH_PROMPT.format(
            word=word, lemma=lemma or word, context=context or word, src=src, tgt=tgt,
        ), max_tokens=512)
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
            provider="openrouter/mistral-nemo",
        )

    def translate_batch(self, blocks, source_lang, target_lang) -> TranslationResult:
        src   = _LANG.get(source_lang, source_lang)
        tgt   = _LANG.get(target_lang, target_lang)
        lines = "\n".join(f"{b['index']}. {b['text']}" for b in blocks)
        raw   = self._call(_TRANSLATE_PROMPT.format(src=src, tgt=tgt, lines=lines), max_tokens=2048)
        data  = json.loads(raw)
        translations = data if isinstance(data, list) else data.get("translations", [])
        return TranslationResult(translations=translations, provider="openrouter/mistral-nemo")
