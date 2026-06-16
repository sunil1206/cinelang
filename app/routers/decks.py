"""Smart deck management — create, list, get words."""
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.dependencies import DBSession, CurrentUser
from app.models.deck import Deck, DeckWord, DECK_TYPES
from app.models.user_vocab import UserVocab

router = APIRouter(prefix="/decks", tags=["Decks"])


@router.get("", summary="List decks for a language")
def list_decks(lang_code: str, db: DBSession, current_user: CurrentUser):
    decks = (
        db.query(Deck)
        .filter(Deck.user_id == current_user.id, Deck.lang_code == lang_code.lower())
        .order_by(Deck.created_at.desc())
        .all()
    )
    return [_deck_out(d) for d in decks]


@router.get("/{deck_id}", summary="Get a deck with its words")
def get_deck(deck_id: int, db: DBSession, current_user: CurrentUser):
    deck = _get_deck(db, deck_id, current_user.id)
    words = (
        db.query(UserVocab)
        .join(DeckWord, DeckWord.user_vocab_id == UserVocab.id)
        .filter(DeckWord.deck_id == deck_id)
        .order_by(DeckWord.order_index)
        .all()
    )
    return {**_deck_out(deck), "words": [_vocab_out(w) for w in words]}


@router.get("/{deck_id}/study", summary="Get due words in study order (SM-2 priority)")
def study_deck(deck_id: int, limit: int = 20, db: DBSession = None, current_user: CurrentUser = None):
    from datetime import datetime, timezone
    deck  = _get_deck(db, deck_id, current_user.id)
    now   = datetime.now(timezone.utc)

    # Priority: overdue → due today → new
    due = (
        db.query(UserVocab)
        .join(DeckWord, DeckWord.user_vocab_id == UserVocab.id)
        .filter(
            DeckWord.deck_id == deck_id,
            UserVocab.next_review <= now,
        )
        .order_by(UserVocab.next_review.asc())
        .limit(limit)
        .all()
    )
    new_words = (
        db.query(UserVocab)
        .join(DeckWord, DeckWord.user_vocab_id == UserVocab.id)
        .filter(
            DeckWord.deck_id == deck_id,
            UserVocab.status == "new",
        )
        .order_by(DeckWord.order_index)
        .limit(max(0, limit - len(due)))
        .all()
    )
    words = due + new_words
    return {"deck": _deck_out(deck), "words": [_vocab_out(w) for w in words], "count": len(words)}


# ── Internal helpers ──────────────────────────────────────────────────────────

def build_decks_from_analysis(
    db,
    user_id: int,
    lang_code: str,
    result,          # AnalysisResult from subtitle_analyzer
    movie_title: str,
) -> list[Deck]:
    """
    Create or update 5 smart decks from SubtitleAnalyzer result.
    Called internally after subtitle analysis.
    """
    created = []
    for deck_type, words in result.deck_groups.items():
        if not words:
            continue

        name = _deck_name(deck_type, movie_title)

        # Find existing deck of this type for this movie
        existing = (
            db.query(Deck)
            .filter(
                Deck.user_id    == user_id,
                Deck.lang_code  == lang_code,
                Deck.deck_type  == deck_type,
                Deck.movie_title == movie_title,
            )
            .first()
        )
        if not existing:
            existing = Deck(
                user_id=user_id, lang_code=lang_code,
                deck_type=deck_type, name=name,
                movie_title=movie_title or None,
            )
            db.add(existing)
            db.flush()

        # Upsert words into user_vocab + deck_words
        for i, w in enumerate(words):
            uv = _upsert_user_vocab(db, user_id, lang_code, w, movie_title)
            # Add to deck if not already there
            exists = db.query(DeckWord).filter(
                DeckWord.deck_id       == existing.id,
                DeckWord.user_vocab_id == uv.id,
            ).first()
            if not exists:
                db.add(DeckWord(deck_id=existing.id, user_vocab_id=uv.id, order_index=i))

        existing.word_count = (
            db.query(DeckWord).filter(DeckWord.deck_id == existing.id).count()
        )
        created.append(existing)

    db.commit()
    return created


def _upsert_user_vocab(db, user_id, lang_code, word, movie_title) -> UserVocab:
    """Insert or return existing UserVocab for this (user, lang, lemma)."""
    existing = (
        db.query(UserVocab)
        .filter(
            UserVocab.user_id   == user_id,
            UserVocab.lang_code  == lang_code,
            UserVocab.lemma      == word.lemma,
        )
        .first()
    )
    if existing:
        return existing

    uv = UserVocab(
        user_id=user_id,
        lang_code=lang_code,
        word=word.word,
        lemma=word.lemma,
        pos=word.pos,
        cefr=word.cefr,
        frequency_zipf=word.zipf,
        ipa=word.ipa or None,
        definition=word.definition or None,
        example=word.example or None,
        translation=word.translation or None,
        source_movie=movie_title or None,
        context_sentence=word.contexts[0] if word.contexts else None,
        status="new",
    )
    db.add(uv)
    db.flush()
    return uv


def _deck_name(deck_type: str, movie_title: str) -> str:
    names = {
        "core":        "Core Vocabulary",
        "movie":       f"Movie Vocab — {movie_title}" if movie_title else "Movie Vocabulary",
        "expressions": f"Expressions — {movie_title}" if movie_title else "Expressions & Idioms",
        "grammar":     "Grammar Patterns",
        "review":      "Daily Review",
    }
    return names.get(deck_type, deck_type.title())


def _get_deck(db, deck_id: int, user_id: int) -> Deck:
    d = db.get(Deck, deck_id)
    if not d or d.user_id != user_id:
        raise HTTPException(404, "Deck not found")
    return d


def _deck_out(d: Deck) -> dict:
    return {
        "id": d.id, "lang_code": d.lang_code, "deck_type": d.deck_type,
        "name": d.name, "movie_title": d.movie_title,
        "word_count": d.word_count,
        "created_at": d.created_at.isoformat(),
    }


def _vocab_out(v: UserVocab) -> dict:
    return {
        "id": v.id, "word": v.word, "lemma": v.lemma,
        "pos": v.pos, "cefr": v.cefr, "status": v.status,
        "translation": v.translation or "", "ipa": v.ipa or "",
        "definition": v.definition or "", "example": v.example or "",
        "mastery_score": v.mastery_score,
        "next_review": v.next_review.isoformat() if v.next_review else None,
        "interval_days": v.interval_days,
        "ease_factor": v.ease_factor,
        "context_sentence": v.context_sentence or "",
        "source_movie": v.source_movie or "",
    }
