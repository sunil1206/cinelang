"""Per-user language profile — one row per (user, language) pair."""
from __future__ import annotations
from datetime import date, datetime
from sqlalchemy import String, Integer, Float, Boolean, Date, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class UserLanguage(Base):
    __tablename__ = "user_languages"

    id:           Mapped[int]          = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id:      Mapped[int]          = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    lang_code:    Mapped[str]          = mapped_column(String(5),  nullable=False)   # 'fr', 'de'
    lang_name:    Mapped[str]          = mapped_column(String(50), nullable=False)   # 'French'
    is_active:    Mapped[bool]         = mapped_column(Boolean, default=False)

    # CEFR progress
    cefr_level:   Mapped[str]          = mapped_column(String(2),  default="A1")     # A1-C1
    cefr_score:   Mapped[float]        = mapped_column(Float,       default=0.0)     # 0-100 within level

    # Gamification
    xp:           Mapped[int]          = mapped_column(Integer, default=0)
    streak_days:  Mapped[int]          = mapped_column(Integer, default=0)
    longest_streak: Mapped[int]        = mapped_column(Integer, default=0)
    last_activity:  Mapped[date | None]= mapped_column(Date,    nullable=True)

    # Goals
    weekly_goal:  Mapped[int]          = mapped_column(Integer, default=10)          # words/week

    # Counters (denormalised for speed)
    total_learned:  Mapped[int]        = mapped_column(Integer, default=0)
    total_known:    Mapped[int]        = mapped_column(Integer, default=0)
    total_mastered: Mapped[int]        = mapped_column(Integer, default=0)

    created_at:   Mapped[datetime]     = mapped_column(DateTime, default=func.now())
    updated_at:   Mapped[datetime]     = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "lang_code", name="uq_user_language"),
    )
