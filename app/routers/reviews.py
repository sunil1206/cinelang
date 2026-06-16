"""Spaced repetition review sessions — SM-2 powered."""
from __future__ import annotations
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.dependencies import DBSession, CurrentUser
from app.models.review import ReviewSession, ReviewItem, RESPONSES
from app.models.user_vocab import UserVocab
from app.models.language_profile import UserLanguage
from app.services.srs.sm2 import update as sm2_update, SRSCard, xp_for_response

router = APIRouter(prefix="/reviews", tags=["Reviews"])


class StartSessionRequest(BaseModel):
    lang_code:    str
    deck_id:      int | None = None
    session_type: str        = "review"   # review / lesson
    limit:        int        = 20


class AnswerRequest(BaseModel):
    user_vocab_id: int
    response:      str    # again / hard / good / easy
    time_ms:       int = 0


@router.get("/due", summary="Get all words due for review today")
def get_due(lang_code: str, limit: int = 50, db: DBSession = None, current_user: CurrentUser = None):
    now = datetime.now(timezone.utc)
    due = (
        db.query(UserVocab)
        .filter(
            UserVocab.user_id   == current_user.id,
            UserVocab.lang_code  == lang_code.lower(),
            UserVocab.next_review <= now,
            UserVocab.status.notin_(["new", "known"]),
        )
        .order_by(UserVocab.next_review.asc())
        .limit(limit)
        .all()
    )
    return {"due_count": len(due), "words": [_vocab_out(w) for w in due]}


@router.post("/session/start", summary="Start a new review session")
def start_session(body: StartSessionRequest, db: DBSession, current_user: CurrentUser):
    lang = body.lang_code.lower()
    now  = datetime.now(timezone.utc)

    # Collect due words
    q = db.query(UserVocab).filter(
        UserVocab.user_id  == current_user.id,
        UserVocab.lang_code == lang,
    )
    if body.deck_id:
        from app.models.deck import DeckWord
        q = q.join(DeckWord, DeckWord.user_vocab_id == UserVocab.id).filter(
            DeckWord.deck_id == body.deck_id
        )

    due_words = (
        q.filter(UserVocab.next_review <= now, UserVocab.status.notin_(["new", "known"]))
        .order_by(UserVocab.next_review.asc())
        .limit(body.limit)
        .all()
    )
    # Top up with new words if session not full
    remaining = body.limit - len(due_words)
    if remaining > 0:
        new_words = (
            q.filter(UserVocab.status == "new")
            .limit(remaining)
            .all()
        )
        due_words = due_words + new_words

    if not due_words:
        raise HTTPException(404, "No words due for review in this language")

    session = ReviewSession(
        user_id=current_user.id,
        lang_code=lang,
        deck_id=body.deck_id,
        session_type=body.session_type,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    return {
        "session_id":  session.id,
        "word_count":  len(due_words),
        "words":       [_vocab_out(w) for w in due_words],
    }


@router.post("/session/{session_id}/answer", summary="Submit one SM-2 answer")
def answer(session_id: int, body: AnswerRequest, db: DBSession, current_user: CurrentUser):
    if body.response not in RESPONSES:
        raise HTTPException(400, f"response must be one of: {RESPONSES}")

    session = db.get(ReviewSession, session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(404, "Session not found")
    if session.completed_at:
        raise HTTPException(400, "Session already completed")

    word = db.get(UserVocab, body.user_vocab_id)
    if not word or word.user_id != current_user.id:
        raise HTTPException(404, "Vocab item not found")

    # Apply SM-2
    card   = SRSCard(
        ease_factor=word.ease_factor,
        interval_days=word.interval_days,
        review_count=word.review_count,
        consecutive_correct=word.consecutive_correct,
        lapse_count=word.lapse_count,
    )
    result = sm2_update(card, body.response)
    xp     = xp_for_response(body.response, word.interval_days)

    # Update UserVocab
    word.ease_factor          = result.ease_factor
    word.interval_days        = result.interval_days
    word.next_review          = result.next_review
    word.status               = result.new_status
    word.review_count         = result.review_count
    word.consecutive_correct  = result.consecutive_correct
    word.lapse_count          = result.lapse_count
    word.mastery_score        = result.mastery_score
    word.last_reviewed        = datetime.now(timezone.utc)
    if body.response in ("good", "easy"):
        word.correct_count += 1

    # Log item
    item = ReviewItem(
        session_id=session_id,
        user_vocab_id=body.user_vocab_id,
        response=body.response,
        time_ms=body.time_ms,
        new_interval=result.interval_days,
        new_ease=result.ease_factor,
    )
    db.add(item)

    # Update session counters
    session.words_reviewed += 1
    if body.response in ("good", "easy"):
        session.correct_count += 1
    session.xp_earned += xp

    # Update language profile XP + counters
    _update_profile_xp(db, current_user.id, word.lang_code, xp, result.new_status)

    db.commit()

    return {
        "word":         word.lemma,
        "new_status":   result.new_status,
        "next_review":  result.next_review.isoformat(),
        "interval_days":result.interval_days,
        "mastery_score":result.mastery_score,
        "xp_earned":    xp,
    }


@router.post("/session/{session_id}/complete", summary="Mark session complete")
def complete_session(session_id: int, db: DBSession, current_user: CurrentUser):
    session = db.get(ReviewSession, session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(404, "Session not found")

    session.completed_at = datetime.now(timezone.utc)
    db.commit()

    accuracy = (
        session.correct_count / session.words_reviewed
        if session.words_reviewed else 0.0
    )
    return {
        "session_id":    session_id,
        "words_reviewed":session.words_reviewed,
        "correct":       session.correct_count,
        "accuracy":      round(accuracy, 2),
        "xp_earned":     session.xp_earned,
        "duration_s":    int((session.completed_at - session.started_at).total_seconds()),
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _update_profile_xp(db, user_id, lang_code, xp, new_status):
    profile = (
        db.query(UserLanguage)
        .filter(UserLanguage.user_id == user_id, UserLanguage.lang_code == lang_code)
        .first()
    )
    if not profile:
        return
    profile.xp += xp
    if new_status == "mastered":
        profile.total_mastered += 1
    elif new_status == "known":
        profile.total_known += 1
    elif new_status in ("learning", "review"):
        profile.total_learned = db.query(UserVocab).filter(
            UserVocab.user_id  == user_id,
            UserVocab.lang_code == lang_code,
            UserVocab.status.in_(["learning", "review", "mastered", "known"]),
        ).count()


def _vocab_out(v: UserVocab) -> dict:
    return {
        "id": v.id, "word": v.word, "lemma": v.lemma,
        "pos": v.pos, "cefr": v.cefr, "status": v.status,
        "translation": v.translation or "", "ipa": v.ipa or "",
        "definition": v.definition or "", "example": v.example or "",
        "context_sentence": v.context_sentence or "",
        "mastery_score": v.mastery_score,
        "interval_days": v.interval_days,
        "next_review": v.next_review.isoformat() if v.next_review else None,
    }
