"""Review sessions and individual item responses."""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base

RESPONSES = ("again", "hard", "good", "easy")


class ReviewSession(Base):
    __tablename__ = "review_sessions"

    id:            Mapped[int]           = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id:       Mapped[int]           = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    lang_code:     Mapped[str]           = mapped_column(String(5),  nullable=False)
    deck_id:       Mapped[int | None]    = mapped_column(ForeignKey("decks.id", ondelete="SET NULL"), nullable=True)
    session_type:  Mapped[str]           = mapped_column(String(20), default="review")  # review/lesson/quiz

    started_at:    Mapped[datetime]      = mapped_column(DateTime, default=func.now())
    completed_at:  Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    words_reviewed: Mapped[int]          = mapped_column(Integer, default=0)
    correct_count:  Mapped[int]          = mapped_column(Integer, default=0)
    xp_earned:      Mapped[int]          = mapped_column(Integer, default=0)

    __table_args__ = (
        Index("ix_review_sessions_user_lang", "user_id", "lang_code", "started_at"),
    )


class ReviewItem(Base):
    __tablename__ = "review_items"

    id:            Mapped[int]  = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id:    Mapped[int]  = mapped_column(ForeignKey("review_sessions.id", ondelete="CASCADE"), nullable=False)
    user_vocab_id: Mapped[int]  = mapped_column(ForeignKey("user_vocab.id", ondelete="CASCADE"), nullable=False)
    response:      Mapped[str]  = mapped_column(String(10), nullable=False)  # again/hard/good/easy
    time_ms:       Mapped[int]  = mapped_column(Integer, default=0)
    shown_at:      Mapped[datetime] = mapped_column(DateTime, default=func.now())

    # Snapshot of SRS state after this response
    new_interval:  Mapped[float] = mapped_column(Integer, default=1)
    new_ease:      Mapped[float] = mapped_column(Integer, default=2)
