"""
Cinema Library router — movies as vocabulary folders.

Endpoints:
  GET    /api/cinema              — list user's movie library
  GET    /api/cinema/{id}/vocab   — vocabulary for a specific movie
  PATCH  /api/cinema/{id}         — update movie metadata (title/year)
  DELETE /api/cinema/{id}         — remove movie (vocab entries kept)
"""
from __future__ import annotations
import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user, get_optional_user
from app.models.movie import Movie
from app.models.vocabulary import VocabEntry
from app.models.user import User

log    = logging.getLogger(__name__)
router = APIRouter(prefix="/cinema", tags=["Cinema"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class MovieOut(BaseModel):
    id:             int
    title:          str
    year:           Optional[int]
    language:       str
    target_lang:    str
    subtitle_count: int
    vocab_count:    int
    cefr_breakdown: dict
    created_at:     str

class WordEntry(BaseModel):
    id:          int
    word:        str
    lemma:       str
    pos:         str
    cefr:        str
    count:       int
    example:     str
    translation: str = ""
    ipa:         str = ""
    explanation: str = ""

class MoviePatch(BaseModel):
    title: Optional[str] = None
    year:  Optional[int] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=list[MovieOut])
def list_movies(
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_optional_user),
):
    """Return all movies in the user's cinema library, most recent first."""
    if not current_user:
        return []
    movies = (
        db.query(Movie)
        .filter(Movie.user_id == current_user.id)
        .order_by(Movie.created_at.desc())
        .all()
    )
    result = []
    for m in movies:
        # Count linked vocab entries
        vc = (
            db.query(VocabEntry)
            .filter(VocabEntry.movie_id == m.id, VocabEntry.user_id == current_user.id)
            .count()
        )
        result.append(MovieOut(
            id=m.id, title=m.title, year=m.year,
            language=m.language, target_lang=m.target_lang,
            subtitle_count=m.subtitle_count,
            vocab_count=vc,
            cefr_breakdown=json.loads(m.cefr_json or "{}"),
            created_at=m.created_at.isoformat(),
        ))
    return result


@router.get("/{movie_id}/vocab", response_model=list[WordEntry])
def movie_vocabulary(
    movie_id:     int,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    """Return all vocabulary entries linked to a specific movie."""
    movie = db.get(Movie, movie_id)
    if not movie or movie.user_id != current_user.id:
        raise HTTPException(404, "Movie not found")

    entries = (
        db.query(VocabEntry)
        .filter(VocabEntry.movie_id == movie_id, VocabEntry.user_id == current_user.id)
        .order_by(VocabEntry.count.desc())
        .all()
    )
    return [
        WordEntry(
            id=e.id,
            word=e.word, lemma=e.lemma or e.word,
            pos=e.pos or "", cefr=e.cefr_level or "B1",
            count=e.count,
            example=e.example_sentence or "",
            translation=e.translation or "",
            ipa=e.phonetic or "",
            explanation=e.explanation or "",
        )
        for e in entries
    ]


@router.get("/{movie_id}/study")
def study_movie_vocab(
    movie_id:     int,
    limit:        int     = 20,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    """Return SM-2 study queue for a specific movie — due + new words."""
    from datetime import datetime, timezone
    from app.models.user_vocab import UserVocab

    movie = db.get(Movie, movie_id)
    if not movie or movie.user_id != current_user.id:
        raise HTTPException(404, "Movie not found")

    now = datetime.now(timezone.utc)
    base = db.query(UserVocab).filter(
        UserVocab.user_id  == current_user.id,
        UserVocab.movie_id == movie_id,
    )
    due = (
        base.filter(UserVocab.next_review <= now, UserVocab.status.notin_(["new", "known"]))
        .order_by(UserVocab.next_review.asc()).limit(limit).all()
    )
    remaining = limit - len(due)
    new_words = (
        base.filter(UserVocab.status == "new").limit(remaining).all()
        if remaining > 0 else []
    )
    words = due + new_words
    return {
        "movie_id": movie_id, "title": movie.title,
        "total": base.count(), "due": len(due), "new": len(new_words),
        "words": [_uv_out(w) for w in words],
    }


def _uv_out(v) -> dict:
    return {
        "id": v.id, "word": v.word, "lemma": v.lemma,
        "pos": v.pos, "cefr": v.cefr, "status": v.status,
        "translation": v.translation or "", "ipa": v.ipa or "",
        "definition": v.definition or "", "example": v.example or "",
        "context_sentence": v.context_sentence or "",
        "mastery_score": v.mastery_score,
        "next_review": v.next_review.isoformat() if v.next_review else None,
    }


@router.patch("/{movie_id}", response_model=MovieOut)
def update_movie(
    movie_id:     int,
    body:         MoviePatch,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    movie = db.get(Movie, movie_id)
    if not movie or movie.user_id != current_user.id:
        raise HTTPException(404, "Movie not found")
    if body.title is not None:
        movie.title = body.title
    if body.year is not None:
        movie.year = body.year
    db.commit()
    db.refresh(movie)
    vc = db.query(VocabEntry).filter(VocabEntry.movie_id == movie_id).count()
    return MovieOut(
        id=movie.id, title=movie.title, year=movie.year,
        language=movie.language, target_lang=movie.target_lang,
        subtitle_count=movie.subtitle_count, vocab_count=vc,
        cefr_breakdown=json.loads(movie.cefr_json or "{}"),
        created_at=movie.created_at.isoformat(),
    )


@router.delete("/{movie_id}", status_code=204)
def delete_movie(
    movie_id:     int,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    """Delete movie record (vocabulary entries are kept in your learning library)."""
    movie = db.get(Movie, movie_id)
    if not movie or movie.user_id != current_user.id:
        raise HTTPException(404, "Movie not found")
    db.delete(movie)
    db.commit()
