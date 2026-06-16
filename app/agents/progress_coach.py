"""
Agent 4 — Progress Coach

Rule-based analytics + optional LLM weekly digest.
$0 cost for all stats. Groq used only for the optional digest text.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@dataclass
class DashboardStats:
    lang_code:      str
    lang_name:      str
    cefr_level:     str
    cefr_score:     float           # 0-100 within level
    xp:             int
    streak_days:    int
    longest_streak: int
    weekly_goal:    int
    words_this_week:int
    total_learned:  int
    total_known:    int
    total_mastered: int
    due_today:      int
    due_this_week:  int
    weak_words:     list[dict] = field(default_factory=list)   # low mastery
    upcoming:       list[dict] = field(default_factory=list)   # next 5 due
    recent_accuracy:float = 0.0
    weekly_xp:      int = 0
    coach_message:  str = ""


def build_dashboard(db, user_id: int, lang_code: str) -> DashboardStats:
    """Compute full dashboard stats from DB. Pure SQL — no LLM."""
    from app.models.language_profile import UserLanguage
    from app.models.user_vocab import UserVocab
    from app.models.review import ReviewSession, ReviewItem
    from sqlalchemy import func

    profile = (
        db.query(UserLanguage)
        .filter(UserLanguage.user_id == user_id, UserLanguage.lang_code == lang_code)
        .first()
    )
    if not profile:
        raise ValueError(f"No language profile for {lang_code}")

    now   = datetime.now(timezone.utc)
    today = now.date()
    week_ago = now - timedelta(days=7)

    # Due counts
    due_today = (
        db.query(func.count(UserVocab.id))
        .filter(
            UserVocab.user_id  == user_id,
            UserVocab.lang_code == lang_code,
            UserVocab.next_review <= now,
            UserVocab.status.notin_(["new", "known"]),
        )
        .scalar() or 0
    )
    due_week = (
        db.query(func.count(UserVocab.id))
        .filter(
            UserVocab.user_id   == user_id,
            UserVocab.lang_code  == lang_code,
            UserVocab.next_review <= now + timedelta(days=7),
            UserVocab.status.notin_(["new", "known"]),
        )
        .scalar() or 0
    )

    # Words studied this week
    words_this_week = (
        db.query(func.count(UserVocab.id))
        .filter(
            UserVocab.user_id   == user_id,
            UserVocab.lang_code  == lang_code,
            UserVocab.last_reviewed >= week_ago,
        )
        .scalar() or 0
    )

    # Weak words — low mastery, status=learning/review
    weak = (
        db.query(UserVocab)
        .filter(
            UserVocab.user_id   == user_id,
            UserVocab.lang_code  == lang_code,
            UserVocab.status.in_(["learning", "review", "lapsed"]),
        )
        .order_by(UserVocab.mastery_score.asc())
        .limit(5)
        .all()
    )

    # Upcoming reviews
    upcoming = (
        db.query(UserVocab)
        .filter(
            UserVocab.user_id   == user_id,
            UserVocab.lang_code  == lang_code,
            UserVocab.next_review > now,
            UserVocab.status.notin_(["new", "known"]),
        )
        .order_by(UserVocab.next_review.asc())
        .limit(5)
        .all()
    )

    # Recent accuracy (last 7 days of review items)
    recent_sessions = (
        db.query(ReviewSession)
        .filter(
            ReviewSession.user_id   == user_id,
            ReviewSession.lang_code  == lang_code,
            ReviewSession.started_at >= week_ago,
            ReviewSession.completed_at.isnot(None),
        )
        .all()
    )
    total_reviewed = sum(s.words_reviewed for s in recent_sessions)
    total_correct  = sum(s.correct_count  for s in recent_sessions)
    accuracy       = (total_correct / total_reviewed) if total_reviewed else 0.0

    # Weekly XP
    weekly_xp = sum(s.xp_earned for s in recent_sessions)

    # Coach message (rule-based)
    message = _coach_message(
        streak=profile.streak_days,
        due=due_today,
        accuracy=accuracy,
        words_this_week=words_this_week,
        weekly_goal=profile.weekly_goal,
    )

    return DashboardStats(
        lang_code=lang_code,
        lang_name=profile.lang_name,
        cefr_level=profile.cefr_level,
        cefr_score=profile.cefr_score,
        xp=profile.xp,
        streak_days=profile.streak_days,
        longest_streak=profile.longest_streak,
        weekly_goal=profile.weekly_goal,
        words_this_week=words_this_week,
        total_learned=profile.total_learned,
        total_known=profile.total_known,
        total_mastered=profile.total_mastered,
        due_today=due_today,
        due_this_week=due_week,
        weak_words=[_vocab_dict(w) for w in weak],
        upcoming=[_vocab_dict(w) for w in upcoming],
        recent_accuracy=round(accuracy, 2),
        weekly_xp=weekly_xp,
        coach_message=message,
    )


def _vocab_dict(v) -> dict:
    return {
        "id": v.id, "word": v.word, "lemma": v.lemma,
        "cefr": v.cefr, "pos": v.pos, "status": v.status,
        "mastery_score": v.mastery_score,
        "next_review": v.next_review.isoformat() if v.next_review else None,
        "translation": v.translation or "",
    }


def _coach_message(streak: int, due: int, accuracy: float, words_this_week: int, weekly_goal: int) -> str:
    """Simple rule-based motivational message."""
    if streak >= 30:
        return f"🔥 Incredible! {streak}-day streak! You're in the top 1% of learners."
    if streak >= 7:
        return f"⚡ {streak} days in a row — your consistency is building real fluency!"
    if due > 20:
        return f"📚 {due} words waiting for review. Clear them to keep your memory sharp!"
    if accuracy >= 0.9:
        return "✨ Excellent accuracy! Time to push to the next CEFR level."
    if accuracy < 0.5 and words_this_week > 0:
        return "💪 Tough session, but every mistake is a learning moment. Slow down and review."
    if words_this_week >= weekly_goal:
        return f"🎯 Weekly goal hit! You've learned {words_this_week} words this week."
    if words_this_week == 0:
        return "👋 Ready for today's lesson? Even 10 minutes builds lasting habits."
    remaining = weekly_goal - words_this_week
    return f"📈 {words_this_week}/{weekly_goal} words this week — {remaining} to go!"
