"""
Groq API service — fast Llama 3.3 70B, generous free tier.
Used as fallback when Gemini is unavailable or quota exceeded.

Free tier: ~6,000 requests/day, ~30 req/min
Get key:   console.groq.com → API Keys → Create API key
"""
from __future__ import annotations
import json
from app.config import get_settings
from app.core.exceptions import ServiceUnavailableError

settings = get_settings()

_LANG_NAMES = {
    "en": "English",  "fr": "French",   "de": "German",   "es": "Spanish",
    "it": "Italian",  "pt": "Portuguese","ja": "Japanese", "ko": "Korean",
    "zh": "Mandarin", "ru": "Russian",   "ar": "Arabic",   "nl": "Dutch",
    "pl": "Polish",   "sv": "Swedish",   "tr": "Turkish",  "hi": "Hindi",
}

_ENRICH_PROMPT = """\
Analyse the {tgt_name} word or phrase: "{word}"
Context sentence: "{context}"

Return a JSON object with exactly these keys:
- translation: {src_name} translation of the word
- pos: part of speech (one of: Noun, Verb, Adjective, Adverb, Idiom, Phrase)
- phonetic: IPA pronunciation guide (e.g. /bɔ̃ʒuʁ/)
- explanation: short usage note or cultural context (1-2 sentences)
- sentence_translation: fluent {src_name} translation of the full context sentence

Respond with only the JSON object, no markdown."""


def _no_key() -> bool:
    return not settings.groq_api_key


def enrich_word(word: str, context: str, source_lang: str, target_lang: str) -> dict:
    """
    Return enrichment dict matching gemini_service.ENRICH_SCHEMA.
    Raises ServiceUnavailableError if Groq is not configured or fails.
    """
    if _no_key():
        raise ServiceUnavailableError("GROQ_API_KEY not configured")

    try:
        from groq import Groq
        client = Groq(api_key=settings.groq_api_key)

        sn = _LANG_NAMES.get(source_lang, source_lang)
        tn = _LANG_NAMES.get(target_lang, target_lang)
        prompt = _ENRICH_PROMPT.format(
            word=word, context=context or word,
            src_name=sn, tgt_name=tn,
        )

        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=512,
            temperature=0.2,
        )
        return json.loads(resp.choices[0].message.content)

    except ServiceUnavailableError:
        raise
    except Exception as exc:
        raise ServiceUnavailableError(f"Groq API error: {exc}") from exc


def translate_batch(
    blocks: list[dict],
    source_lang: str,
    target_lang: str,
) -> dict:
    """
    Translate subtitle blocks via Groq.
    Only called when both Gemini and deep-translator fail.
    Returns dict matching gemini_service.TRANSLATE_SCHEMA.
    """
    if _no_key():
        raise ServiceUnavailableError("GROQ_API_KEY not configured")

    try:
        from groq import Groq
        client = Groq(api_key=settings.groq_api_key)

        sn = _LANG_NAMES.get(source_lang, source_lang)
        tn = _LANG_NAMES.get(target_lang, target_lang)
        numbered = "\n".join(f"{b['index']}. {b['text']}" for b in blocks)

        prompt = (
            f"Translate these {sn} subtitles into {tn}. "
            f"Return JSON with key 'translations' as array of {{index, text}} objects.\n\n"
            f"{numbered}"
        )
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=2048,
            temperature=0.1,
        )
        data = json.loads(resp.choices[0].message.content)
        return {"translations": data.get("translations", []), "vocabulary": []}

    except ServiceUnavailableError:
        raise
    except Exception as exc:
        raise ServiceUnavailableError(f"Groq translate error: {exc}") from exc
