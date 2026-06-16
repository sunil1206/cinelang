"""Language profile management — activation, dashboard, streak."""
from __future__ import annotations
from datetime import date, datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.dependencies import DBSession, CurrentUser
from app.models.language_profile import UserLanguage

router = APIRouter(prefix="/languages", tags=["Languages"])

_SUPPORTED = {
    "fr": "French", "de": "German", "es": "Spanish", "it": "Italian",
    "pt": "Portuguese", "nl": "Dutch", "ja": "Japanese", "ko": "Korean",
    "zh": "Chinese", "ru": "Russian", "ar": "Arabic", "en": "English",
}


class ActivateRequest(BaseModel):
    cefr_level:  str = "A1"
    weekly_goal: int = 10


@router.get("", summary="List user's active languages")
def list_languages(db: DBSession, current_user: CurrentUser):
    profiles = (
        db.query(UserLanguage)
        .filter(UserLanguage.user_id == current_user.id)
        .order_by(UserLanguage.is_active.desc(), UserLanguage.created_at)
        .all()
    )
    return [_profile_out(p) for p in profiles]


@router.post("/{lang_code}/activate", summary="Activate a language for learning")
def activate_language(
    lang_code: str,
    body: ActivateRequest,
    db: DBSession,
    current_user: CurrentUser,
):
    code = lang_code.lower()[:5]
    name = _SUPPORTED.get(code)
    if not name:
        raise HTTPException(400, f"Unsupported language: {code}")
    if body.cefr_level not in ("A1", "A2", "B1", "B2", "C1"):
        raise HTTPException(400, "cefr_level must be A1/A2/B1/B2/C1")

    existing = (
        db.query(UserLanguage)
        .filter(UserLanguage.user_id == current_user.id, UserLanguage.lang_code == code)
        .first()
    )
    if existing:
        existing.is_active   = True
        existing.cefr_level  = body.cefr_level
        existing.weekly_goal = body.weekly_goal
        db.commit()
        return _profile_out(existing)

    profile = UserLanguage(
        user_id=current_user.id,
        lang_code=code,
        lang_name=name,
        is_active=True,
        cefr_level=body.cefr_level,
        weekly_goal=body.weekly_goal,
    )
    # Set all others inactive (one active language at a time)
    db.query(UserLanguage).filter(
        UserLanguage.user_id == current_user.id
    ).update({"is_active": False})

    db.add(profile)
    db.commit()
    db.refresh(profile)
    return _profile_out(profile)


@router.get("/{lang_code}/dashboard", summary="Full dashboard stats for a language")
def dashboard(lang_code: str, db: DBSession, current_user: CurrentUser):
    from app.agents.progress_coach import build_dashboard
    try:
        stats = build_dashboard(db, current_user.id, lang_code.lower())
    except ValueError as e:
        raise HTTPException(404, str(e))
    return stats


@router.post("/{lang_code}/streak", summary="Record today's activity and update streak")
def record_activity(lang_code: str, db: DBSession, current_user: CurrentUser):
    profile = _get_profile(db, current_user.id, lang_code)
    today   = date.today()

    if profile.last_activity == today:
        return _profile_out(profile)  # already recorded today

    if profile.last_activity == today - __import__("datetime").timedelta(days=1):
        profile.streak_days += 1
    else:
        profile.streak_days = 1   # reset

    profile.longest_streak = max(profile.longest_streak, profile.streak_days)
    profile.last_activity   = today
    db.commit()
    return _profile_out(profile)


@router.patch("/{lang_code}/settings", summary="Update language settings")
def update_settings(
    lang_code: str,
    body: ActivateRequest,
    db: DBSession,
    current_user: CurrentUser,
):
    profile = _get_profile(db, current_user.id, lang_code)
    if body.cefr_level:
        profile.cefr_level  = body.cefr_level
    if body.weekly_goal:
        profile.weekly_goal = body.weekly_goal
    db.commit()
    return _profile_out(profile)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_profile(db, user_id: int, lang_code: str) -> UserLanguage:
    p = (
        db.query(UserLanguage)
        .filter(UserLanguage.user_id == user_id, UserLanguage.lang_code == lang_code.lower())
        .first()
    )
    if not p:
        raise HTTPException(404, f"Language {lang_code} not activated")
    return p


def _profile_out(p: UserLanguage) -> dict:
    return {
        "lang_code":      p.lang_code,
        "lang_name":      p.lang_name,
        "is_active":      p.is_active,
        "cefr_level":     p.cefr_level,
        "cefr_score":     p.cefr_score,
        "xp":             p.xp,
        "streak_days":    p.streak_days,
        "longest_streak": p.longest_streak,
        "weekly_goal":    p.weekly_goal,
        "total_learned":  p.total_learned,
        "total_known":    p.total_known,
        "total_mastered": p.total_mastered,
        "last_activity":  p.last_activity.isoformat() if p.last_activity else None,
    }
