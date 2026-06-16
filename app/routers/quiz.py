"""Quiz generation endpoint — template-based, no LLM required."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.dependencies import DBSession, CurrentUser, get_db, get_current_user
from app.models.user_vocab import UserVocab
from app.models.user import User
from app.agents.quiz_generator import generate_session

router = APIRouter(prefix="/quiz", tags=["Quiz"])


class QuizRequest(BaseModel):
    lang_code:    str
    deck_id:      int | None = None
    size:         int        = 10
    cefr_filter:  str | None = None   # "A1", "B1" etc — restrict to one level


@router.get("/movie/{movie_id}", summary="Quiz for a specific movie")
def quiz_for_movie(
    movie_id: int, size: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.movie import Movie
    movie = db.get(Movie, movie_id)
    if not movie or movie.user_id != current_user.id:
        raise HTTPException(404, "Movie not found")
    vocab = db.query(UserVocab).filter(
        UserVocab.user_id  == current_user.id,
        UserVocab.movie_id == movie_id,
        UserVocab.translation.isnot(None),
    ).order_by(UserVocab.mastery_score.asc()).limit(size * 4).all()
    if len(vocab) < 2:
        raise HTTPException(400, "Not enough vocabulary for this movie yet — translate subtitles first")
    items = [_uv_to_dict(v) for v in vocab]
    questions = generate_session(items, size=min(size, len(items)))
    return {"movie_id": movie_id, "title": movie.title,
            "count": len(questions), "questions": [_q_out(q) for q in questions]}


@router.get("/book/{book_id}", summary="Quiz for a specific book")
def quiz_for_book(
    book_id: int, size: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.book import BookLibrary
    book = db.get(BookLibrary, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404, "Book not found")
    vocab = db.query(UserVocab).filter(
        UserVocab.user_id == current_user.id,
        UserVocab.book_id == book_id,
        UserVocab.translation.isnot(None),
    ).order_by(UserVocab.mastery_score.asc()).limit(size * 4).all()
    if len(vocab) < 2:
        raise HTTPException(400, "Not enough vocabulary for this book yet")
    items = [_uv_to_dict(v) for v in vocab]
    questions = generate_session(items, size=min(size, len(items)))
    return {"book_id": book_id, "title": book.title,
            "count": len(questions), "questions": [_q_out(q) for q in questions]}


def _uv_to_dict(v: UserVocab) -> dict:
    return {
        "word": v.word, "lemma": v.lemma, "pos": v.pos, "cefr": v.cefr,
        "translation": v.translation or "", "ipa": v.ipa or "",
        "definition": v.definition or "", "example": v.example or "",
        "context_sentence": v.context_sentence or "", "mastery_score": v.mastery_score,
    }


def _q_out(q) -> dict:
    return {
        "type": q.q_type, "prompt": q.prompt, "answer": q.answer,
        "options": q.options, "hint": q.hint, "word": q.word, "cefr": q.cefr,
    }


@router.post("/generate", summary="Generate a quiz session")
def generate_quiz(body: QuizRequest, db: DBSession, current_user: CurrentUser):
    lang = body.lang_code.lower()
    q    = db.query(UserVocab).filter(
        UserVocab.user_id   == current_user.id,
        UserVocab.lang_code  == lang,
        UserVocab.status.in_(["learning", "review", "mastered"]),
        UserVocab.translation.isnot(None),
    )
    if body.cefr_filter:
        q = q.filter(UserVocab.cefr == body.cefr_filter.upper())
    if body.deck_id:
        from app.models.deck import DeckWord
        q = q.join(DeckWord, DeckWord.user_vocab_id == UserVocab.id).filter(
            DeckWord.deck_id == body.deck_id
        )

    vocab = q.order_by(UserVocab.mastery_score.asc()).limit(body.size * 4).all()
    if len(vocab) < 3:
        raise HTTPException(400, "Not enough vocabulary to generate a quiz — study more words first")

    quiz_items = generate_session(vocab, size=min(body.size, len(vocab)))
    return {"lang_code": lang, "count": len(quiz_items), "questions": quiz_items}
