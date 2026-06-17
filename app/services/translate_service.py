"""
Translation service — deep-translator (Google) primary, DeepL optional upgrade.

Priority:
  1. DeepL (if DEEPL_API_KEY set) — best quality for EU languages
  2. Google Translate via deep-translator — reliable, no key, no daily limit
  3. Source text echo — if both fail (never leaves the user with an error)
"""
from __future__ import annotations
import re
from app.config import get_settings

settings = get_settings()

# Stage-direction pattern — keep as-is, don't translate
_STAGE_RE = re.compile(r"^\[.*?\]$")


def _mymemory(text: str, src: str, tgt: str) -> str | None:
    """MyMemory free API — reliable, no key, 10K chars/day."""
    try:
        import httpx
        r = httpx.get(
            "https://api.mymemory.translated.net/get",
            params={"q": text[:500], "langpair": f"{src}|{tgt}"},
            timeout=6.0,
        )
        data = r.json()
        if data.get("responseStatus") == 200:
            t = data.get("responseData", {}).get("translatedText", "")
            if t and t.lower() != text.lower():
                return t
    except Exception:
        pass
    return None


def _google(text: str, src: str, tgt: str) -> str | None:
    try:
        from deep_translator import GoogleTranslator
        return GoogleTranslator(source=src, target=tgt).translate(text) or None
    except Exception:
        return None


def _deepl(text: str, src: str, tgt: str) -> str | None:
    if not settings.deepl_api_key:
        return None
    try:
        from deep_translator import DeeplTranslator
        return DeeplTranslator(
            api_key=settings.deepl_api_key,
            source=src,
            target=tgt,
            use_free_api=True,
        ).translate(text) or None
    except Exception:
        return None


def translate_text(text: str, source_lang: str, target_lang: str) -> str:
    """Translate a single string. Returns source text if all backends fail."""
    stripped = text.strip()
    if not stripped or source_lang == target_lang:
        return text
    if _STAGE_RE.match(stripped):
        return text

    # Google Translate (primary, free) → MyMemory → DeepL (if key valid)
    result = _google(stripped, source_lang, target_lang)
    if not result:
        result = _mymemory(stripped, source_lang, target_lang)
    if not result:
        result = _deepl(stripped, source_lang, target_lang)
    return result or text


def translate_batch(
    blocks: list[dict],
    source_lang: str,
    target_lang: str,
) -> dict:
    """
    Translate a list of subtitle blocks.
    Returns dict compatible with gemini_service.TRANSLATE_SCHEMA (no vocabulary).
    """
    translations = []
    for b in blocks:
        translated = translate_text(b["text"], source_lang, target_lang)
        translations.append({"index": b["index"], "text": translated})
    return {"translations": translations, "vocabulary": []}
