"""Anthropic Claude provider — claude-haiku-4 (fast, cheap, excellent quality)."""
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
You are a language expert. Analyse the {tgt} word: "{word}" (lemma: "{lemma}")
Context sentence: "{context}"

Return ONLY a valid JSON object — no explanation, no markdown, just JSON:
{{
  "translation": "{src} translation of the word",
  "phonetic": "IPA pronunciation e.g. /bɔ̃ʒuʁ/",
  "partOfSpeech": "Noun|Verb|Adjective|Adverb|Idiom|Phrase|Slang",
  "cefrLevel": "A1|A2|B1|B2|C1",
  "frequencyRank": "very common|common|uncommon|rare",
  "exampleSentence": "natural {tgt} example sentence using this word",
  "sentenceTranslation": "{src} translation of that example sentence",
  "isIdiom": false,
  "isSlang": false,
  "explanation": "1-2 sentence cultural or usage note"
}}"""

_TRANSLATE_PROMPT = """\
Translate the following {src} subtitle lines to {tgt}.
Return ONLY valid JSON — no markdown, no explanation:
{{"translations": [{{"index": 1, "text": "translated text"}}]}}

Subtitle lines:
{lines}"""


class AnthropicProvider(BaseProvider):
    name = ProviderName.ANTHROPIC

    def __init__(self):
        self._settings = get_settings()

    def is_available(self) -> bool:
        key = self._settings.anthropic_api_key
        return bool(key and len(key) > 10)

    def _call(self, prompt: str, max_tokens: int = 1024) -> str:
        import anthropic
        client = anthropic.Anthropic(api_key=self._settings.anthropic_api_key)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        text = msg.content[0].text.strip()

        # Strip markdown fences if any
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if len(lines) > 2 else text

        # Extract JSON object
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            text = match.group(0)
        return text

    def enrich_word(self, word, lemma, context, source_lang, target_lang) -> VocabResult:
        src = _LANG.get(source_lang, source_lang)
        tgt = _LANG.get(target_lang, target_lang)
        raw  = self._call(_ENRICH_PROMPT.format(
            word=word, lemma=lemma or word,
            context=context or word,
            src=src, tgt=tgt,
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
            provider="claude-haiku-4",
        )

    def translate_batch(self, blocks, source_lang, target_lang) -> TranslationResult:
        src   = _LANG.get(source_lang, source_lang)
        tgt   = _LANG.get(target_lang, target_lang)
        lines = "\n".join(f"{b['index']}. {b['text']}" for b in blocks)
        raw   = self._call(_TRANSLATE_PROMPT.format(src=src, tgt=tgt, lines=lines), max_tokens=2048)
        data  = json.loads(raw)
        translations = data if isinstance(data, list) else data.get("translations", [])
        return TranslationResult(translations=translations, provider="claude-haiku-4")
