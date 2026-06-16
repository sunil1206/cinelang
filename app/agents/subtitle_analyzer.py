"""
Agent 1 — Subtitle Analyzer

Runs the full NLP pipeline on uploaded subtitles, detects idioms/expressions
via LLM (Groq, only for non-trivial content), and generates 5 smart decks.

Cost: $0 for standard vocab. LLM only for idiom/expression detection.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.services.nlp.pipeline import run as nlp_run, ExtractedWord
from app.services.nlp.cefr import cefr_rank

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from app.models.user import User

DECK_TYPES = {
    "core":        "Core Vocabulary",
    "movie":       "Movie Vocabulary",
    "expressions": "Expressions & Idioms",
    "grammar":     "Grammar Patterns",
    "review":      "Review Deck",
}

_POS_TO_DECK = {
    "Verb":      "grammar",
    "Adjective": "movie",
    "Adverb":    "movie",
    "Noun":      "movie",
    "Idiom":     "expressions",
    "Phrase":    "expressions",
}


@dataclass
class AnalysisResult:
    words:          list[ExtractedWord]
    new_word_count: int
    deck_groups:    dict[str, list[ExtractedWord]]
    detected_lang:  str
    movie_title:    str


def analyze(
    subtitle_frames: list[dict],
    lang_code: str,
    user_cefr: str = "A1",
    known_lemmas: set[str] | None = None,
    movie_title: str = "",
    enrich_idioms: bool = True,
) -> AnalysisResult:
    """
    Full analysis pipeline. Returns vocab + deck assignments.

    1. NLP pipeline (spaCy + wordfreq + Wiktionary) — always free
    2. LLM idiom detection (Groq) — optional, only top-30 words
    """
    # ── Step 1: Core NLP pipeline ─────────────────────────────────────────────
    words = nlp_run(
        subtitle_frames=subtitle_frames,
        lang_code=lang_code,
        known_lemmas=known_lemmas,
        user_cefr=user_cefr,
        max_new=60,
    )

    # ── Step 2: LLM idiom/expression detection (optional) ────────────────────
    if enrich_idioms and words:
        words = _detect_idioms(words[:30], lang_code)

    # ── Step 3: Assign to deck types ─────────────────────────────────────────
    deck_groups: dict[str, list[ExtractedWord]] = {k: [] for k in DECK_TYPES}
    user_rank = cefr_rank(user_cefr)

    for w in words:
        word_rank = cefr_rank(w.cefr)
        if w.is_idiom:
            deck_groups["expressions"].append(w)
        elif w.pos in ("Verb",) and word_rank <= user_rank + 1:
            deck_groups["grammar"].append(w)
        elif word_rank <= 2:   # A1-A2 → core
            deck_groups["core"].append(w)
        else:
            deck_groups["movie"].append(w)

    return AnalysisResult(
        words=words,
        new_word_count=len(words),
        deck_groups=deck_groups,
        detected_lang=lang_code,
        movie_title=movie_title,
    )


def _detect_idioms(words: list[ExtractedWord], lang_code: str) -> list[ExtractedWord]:
    """
    Use Groq to flag idioms and expressions among the extracted words.
    Falls back gracefully — never crashes the pipeline.
    """
    try:
        from app.services.groq_service import _no_key
        if _no_key():
            return words

        from groq import Groq
        from app.config import get_settings
        import json

        settings = get_settings()
        client   = Groq(api_key=settings.groq_api_key)

        word_list = [w.lemma for w in words]
        prompt = (
            f"From this list of {lang_code.upper()} words/lemmas, identify which are "
            f"idiomatic expressions, fixed phrases, or culturally specific terms "
            f"(NOT simple nouns/verbs/adjectives): {word_list}\n\n"
            f"Return JSON: {{\"idioms\": [list of word strings that are idiomatic]}}"
        )
        resp   = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=256,
            temperature=0,
        )
        idioms = set(json.loads(resp.choices[0].message.content).get("idioms", []))
        for w in words:
            if w.lemma in idioms:
                w.is_idiom = True
                w.pos      = "Idiom"
    except Exception:
        pass

    return words
