"""Daily lesson planning endpoint."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.dependencies import DBSession, CurrentUser
from app.models.language_profile import UserLanguage
from app.agents.learning_planner import generate

router = APIRouter(prefix="/lessons", tags=["Lessons"])

_CEFR_NEXT = {"A1": "A2", "A2": "B1", "B1": "B2", "B2": "C1", "C1": "C1"}


class PlanRequest(BaseModel):
    lang_code:    str
    days:         int  = 30
    weak_areas:   list[str] = []


@router.post("/plan", summary="Generate a learning plan for the next N days")
def get_plan(body: PlanRequest, db: DBSession, current_user: CurrentUser):
    lang = body.lang_code.lower()
    profile = (
        db.query(UserLanguage)
        .filter(UserLanguage.user_id == current_user.id, UserLanguage.lang_code == lang)
        .first()
    )
    if not profile:
        raise HTTPException(404, f"Language {lang} not activated — activate it first")

    target = _CEFR_NEXT.get(profile.cefr_level, "C1")
    plan   = generate(
        lang_code    = lang,
        lang_name    = profile.lang_name,
        cefr_current = profile.cefr_level,
        cefr_target  = target,
        weak_areas   = body.weak_areas or [],
        days         = body.days,
    )
    return {
        "lang_code":   plan.lang_code,
        "lang_name":   plan.lang_name,
        "cefr_start":  plan.cefr_start,
        "cefr_target": plan.cefr_target,
        "overview":    plan.overview,
        "days":        [
            {
                "day":          d.day,
                "focus":        d.focus,
                "new_words":    d.new_words,
                "review_words": d.review_words,
                "grammar_tip":  d.grammar_tip,
                "goal":         d.goal,
            }
            for d in plan.days
        ],
    }


@router.get("/today", summary="Get today's lesson plan for active language")
def today_lesson(lang_code: str, db: DBSession, current_user: CurrentUser):
    """Returns today's session summary: due words + new batch + tip."""
    from datetime import datetime, timezone
    from app.models.user_vocab import UserVocab

    lang = lang_code.lower()
    now  = datetime.now(timezone.utc)

    due_count = (
        db.query(UserVocab)
        .filter(
            UserVocab.user_id   == current_user.id,
            UserVocab.lang_code  == lang,
            UserVocab.next_review <= now,
            UserVocab.status.notin_(["new", "known"]),
        )
        .count()
    )
    new_count = (
        db.query(UserVocab)
        .filter(
            UserVocab.user_id   == current_user.id,
            UserVocab.lang_code  == lang,
            UserVocab.status     == "new",
        )
        .count()
    )

    profile = (
        db.query(UserLanguage)
        .filter(UserLanguage.user_id == current_user.id, UserLanguage.lang_code == lang)
        .first()
    )

    return {
        "lang_code":    lang,
        "cefr_level":   profile.cefr_level if profile else "A1",
        "due_reviews":  due_count,
        "new_available":new_count,
        "recommended_new": 10,
        "tip": _tip_for_cefr(profile.cefr_level if profile else "A1"),
    }


def _tip_for_cefr(level: str) -> str:
    tips = {
        "A1": "Focus on everyday words: greetings, numbers, colours, family.",
        "A2": "Try to use new words in short sentences when you review them.",
        "B1": "Read simple news articles in the target language — 10 mins/day.",
        "B2": "Practice with authentic podcasts or YouTube videos with subtitles.",
        "C1": "Read literature in the target language and note idioms you encounter.",
    }
    return tips.get(level, "Keep practising — consistency beats intensity!")
