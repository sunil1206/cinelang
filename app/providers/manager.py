"""
ProviderManager — resilient multi-provider AI system.

Priority: Groq → Gemini → Ollama → Offline

Features:
  - Circuit breaker per provider (opens after 3 consecutive failures)
  - Exponential backoff on retry
  - Timeout isolation (each provider has its own timeout)
  - Redis cache check before any AI call
  - Never raises to the caller — always returns a result
"""
from __future__ import annotations
import logging
import time
from dataclasses import dataclass, field
from threading import Lock

from app.providers.base import BaseProvider, VocabResult, TranslationResult
from app.providers.anthropic_provider import AnthropicProvider
from app.providers.openai_provider import OpenAIProvider
from app.providers.groq_provider import GroqProvider
from app.providers.gemini_provider import GeminiProvider
from app.providers.openrouter_provider import OpenRouterProvider
from app.providers.ollama_provider import OllamaProvider
from app.providers.offline_provider import OfflineProvider
from app.providers.dictionary_provider import DictionaryProvider

log = logging.getLogger(__name__)

# ── Circuit breaker state ──────────────────────────────────────────────────────

@dataclass
class CircuitBreaker:
    failure_threshold: int   = 3
    reset_timeout_s:   float = 300.0   # 5 min before retrying a failed provider
    _failures:         int   = field(default=0, init=False)
    _opened_at:        float = field(default=0.0, init=False)
    _lock:             Lock  = field(default_factory=Lock, init=False)

    def is_open(self) -> bool:
        with self._lock:
            if self._failures >= self.failure_threshold:
                if time.time() - self._opened_at > self.reset_timeout_s:
                    # half-open: allow one attempt
                    self._failures = self.failure_threshold - 1
                    return False
                return True
            return False

    def record_success(self):
        with self._lock:
            self._failures = 0

    def record_failure(self):
        with self._lock:
            self._failures += 1
            if self._failures >= self.failure_threshold:
                self._opened_at = time.time()
                log.warning("Circuit opened for provider after %d failures", self._failures)


# ── Cache helper ───────────────────────────────────────────────────────────────

def _cache_get(key: str) -> dict | None:
    try:
        from app.cache.redis_cache import get as redis_get
        return redis_get(key)
    except Exception:
        return None


def _cache_set(key: str, value: dict) -> None:
    try:
        from app.cache.redis_cache import set as redis_set
        redis_set(key, value)
    except Exception:
        pass


# ── ProviderManager ────────────────────────────────────────────────────────────

class ProviderManager:
    """
    Manages the provider fallback chain and circuit breakers.
    Singleton — import `provider_manager` instead of instantiating.
    """

    def __init__(self):
        self._providers: list[BaseProvider] = [
            OpenAIProvider(),      # 1 — gpt-4o-mini (paid, best quality)
            AnthropicProvider(),   # 2 — Claude Haiku
            GeminiProvider(),      # 3 — Gemini 2.5 Flash (free key)
            GroqProvider(),        # 4 — Llama 3.3 70B
            OpenRouterProvider(),  # 5 — free models
            DictionaryProvider(),  # 6 — MyMemory + FreeDictionary + Wiktionary (no key)
            OllamaProvider(),      # 7 — local Ollama
            OfflineProvider(),     # 8 — offline dict + Google Translate
        ]
        self._breakers: dict[str, CircuitBreaker] = {
            p.name.value: CircuitBreaker() for p in self._providers
        }
        # Permanently banned this session (auth error / quota exhausted — no point retrying)
        self._banned: set[str] = set()

    # ── Public API ─────────────────────────────────────────────────────────────

    def enrich_word(
        self,
        word: str,
        lemma: str   = "",
        context: str = "",
        source_lang: str = "en",
        target_lang: str = "fr",
    ) -> dict:
        cache_key = f"vocab:{target_lang}:{lemma or word}"
        cached = _cache_get(cache_key)
        if cached:
            cached["_cache"] = True
            return cached

        result = self._try_providers_enrich(word, lemma or word, context, source_lang, target_lang)
        out = result.to_dict()
        _cache_set(cache_key, out)
        return out

    def translate_batch(
        self,
        blocks: list[dict],
        source_lang: str = "fr",
        target_lang: str = "en",
    ) -> TranslationResult:
        # Translation is not cached (too large / dynamic)
        return self._try_providers_translate(blocks, source_lang, target_lang)

    def status(self) -> dict:
        return {
            name: {
                "available": p.is_available(),
                "circuit_open": self._breakers[p.name.value].is_open(),
            }
            for p, name in ((p, p.name.value) for p in self._providers)
        }

    def reset_circuits(self) -> None:
        for breaker in self._breakers.values():
            with breaker._lock:
                breaker._failures = 0
                breaker._opened_at = 0.0

    # ── Internal fallback chain ────────────────────────────────────────────────

    def _try_providers_enrich(
        self, word, lemma, context, source_lang, target_lang
    ) -> VocabResult:
        for provider in self._providers:
            name = provider.name.value
            breaker = self._breakers[name]

            if name in self._banned:
                continue
            if not provider.is_available():
                continue
            if breaker.is_open():
                continue

            try:
                result = provider.enrich_word(word, lemma, context, source_lang, target_lang)
                breaker.record_success()
                log.debug("enrich_word served by %s", name)
                return result
            except Exception as exc:
                err_str = str(exc).lower()
                _AUTH_KEYS = ("401", "403", "restricted", "unauthorized", "forbidden",
                              "insufficient_quota", "quota", "billing")
                if any(k in err_str for k in _AUTH_KEYS):
                    self._banned.add(name)
                    log.warning("Provider %s permanently banned this session: %s", name, str(exc)[:120])
                elif "400" in err_str and "organization" in err_str:
                    self._banned.add(name)
                    log.warning("Provider %s org-banned: %s", name, str(exc)[:120])
                else:
                    breaker.record_failure()
                    log.warning("Provider %s failed enrich_word: %s", name, exc)

        # Should never reach here — OfflineProvider always succeeds
        return OfflineProvider().enrich_word(word, lemma, context, source_lang, target_lang)

    def _try_providers_translate(
        self, blocks, source_lang, target_lang
    ) -> TranslationResult:
        # Try deep-translator first (free, no key, reliable)
        try:
            from app.services.translate_service import translate_batch as deep_translate
            result = deep_translate(blocks, source_lang, target_lang)
            if result and result.get("translations"):
                return TranslationResult(
                    translations=result["translations"],
                    provider="deep-translator",
                )
        except Exception as exc:
            log.warning("deep-translator failed: %s", exc)

        # Then AI providers
        for provider in self._providers[:-1]:  # skip offline for translation
            name = provider.name.value
            breaker = self._breakers[name]

            if not provider.is_available():
                continue
            if breaker.is_open():
                continue

            try:
                result = provider.translate_batch(blocks, source_lang, target_lang)
                breaker.record_success()
                log.debug("translate_batch served by %s", name)
                return result
            except Exception as exc:
                err_str = str(exc).lower()
                if any(k in err_str for k in ("400", "401", "403", "restricted", "unauthorized", "forbidden")):
                    breaker._failures = breaker.failure_threshold
                    breaker._opened_at = __import__("time").time()
                    log.warning("Provider %s hard-disabled (auth/restriction error)", name)
                else:
                    breaker.record_failure()
                log.warning("Provider %s failed translate_batch: %s", name, exc)

        # Final: offline echo
        return OfflineProvider().translate_batch(blocks, source_lang, target_lang)


# Singleton instance
provider_manager = ProviderManager()
