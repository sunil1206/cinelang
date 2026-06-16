"""
LangChain-powered Book Vocabulary Agent.

Uses OpenAI gpt-4o-mini as primary (with fallback to offline+Google).
Enriches a batch of words with: translation, IPA, part-of-speech, CEFR, example.
"""
from __future__ import annotations
import json
import logging
import re
from typing import Any

log = logging.getLogger(__name__)


# ── Prompts ────────────────────────────────────────────────────────────────────

_SYSTEM = (
    "You are a French language expert. Given a list of French words from a book, "
    "return enrichment data as a JSON array. For each word provide:\n"
    "- word (string)\n"
    "- translation (English meaning)\n"
    "- ipa (IPA phonetic, e.g. /ʃɑ̃/)\n"
    "- pos (Noun/Verb/Adjective/Adverb/Other)\n"
    "- cefr (A1/A2/B1/B2/C1)\n"
    "- example (short French example sentence using the word)\n"
    "- mnemonic (one short memory trick in English)\n\n"
    "Return ONLY the JSON array, no markdown fences."
)

_HUMAN = "Enrich these French words: {words_json}"


def _parse_json_response(text: str) -> list[dict]:
    """Extract JSON array from LLM response, stripping markdown if needed."""
    text = text.strip()
    # Strip markdown fences
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    # Find array
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        text = match.group(0)
    return json.loads(text)


# ── Main agent function ────────────────────────────────────────────────────────

def enrich_words_with_langchain(
    words: list[dict],  # [{"word": ..., "lemma": ..., "example": ...}, ...]
    source_lang: str = "fr",
    target_lang: str = "en",
    batch_size: int = 15,
) -> list[dict]:
    """
    Enrich a list of word dicts using LangChain + OpenAI gpt-4o-mini.
    Falls back to the provider_manager (offline+Google) on failure.
    Returns the input list with enrichment fields merged in.
    """
    from app.config import get_settings
    settings = get_settings()

    if not settings.openai_api_key:
        log.warning("OpenAI key not set — falling back to provider_manager")
        return _fallback_enrich(words)

    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import SystemMessage, HumanMessage

        llm = ChatOpenAI(
            model="gpt-4o-mini",
            api_key=settings.openai_api_key,
            temperature=0,
            max_tokens=2000,
            timeout=30,
        )

        enriched: list[dict] = []

        # Process in batches
        for i in range(0, len(words), batch_size):
            batch = words[i:i + batch_size]
            word_list = [
                {"word": w.get("word", w.get("lemma", "")), "context": w.get("example", "")[:80]}
                for w in batch
            ]

            messages = [
                SystemMessage(content=_SYSTEM),
                HumanMessage(content=_HUMAN.format(words_json=json.dumps(word_list, ensure_ascii=False))),
            ]

            try:
                response = llm.invoke(messages)
                results = _parse_json_response(response.content)

                # Merge enrichment back onto original word dicts
                result_map = {r.get("word", "").lower(): r for r in results}
                for w in batch:
                    key = w.get("word", w.get("lemma", "")).lower()
                    enrichment = result_map.get(key) or result_map.get(w.get("lemma", "").lower(), {})
                    enriched.append({**w, **_normalize(enrichment)})

            except Exception as exc:
                log.warning("LangChain batch %d failed: %s", i, exc)
                enriched.extend(batch)  # keep originals on failure

        log.info("LangChain enriched %d words via OpenAI gpt-4o-mini", len(enriched))
        return enriched

    except ImportError:
        log.warning("langchain_openai not installed — run: pip install langchain-openai")
        return _fallback_enrich(words)
    except Exception as exc:
        log.warning("LangChain agent failed: %s", exc)
        return _fallback_enrich(words)


def _normalize(e: dict) -> dict:
    """Normalise enrichment field names to match our DB schema."""
    return {
        "translation": e.get("translation", ""),
        "ipa":         e.get("ipa", ""),
        "pos":         e.get("pos", ""),
        "cefr":        e.get("cefr", "B1"),
        "example":     e.get("example", ""),
        "mnemonic":    e.get("mnemonic", ""),
    }


def _fallback_enrich(words: list[dict]) -> list[dict]:
    """Fallback: use the existing provider_manager (offline+Google Translate)."""
    try:
        from app.providers.manager import provider_manager
        enriched = []
        for w in words:
            try:
                result = provider_manager.enrich_word(
                    word=w.get("word", ""),
                    lemma=w.get("lemma", ""),
                    context=w.get("example", ""),
                    source_lang="fr",
                    target_lang="en",
                )
                enriched.append({**w, **result})
            except Exception:
                enriched.append(w)
        return enriched
    except Exception as exc:
        log.warning("Fallback enrich failed: %s", exc)
        return words
