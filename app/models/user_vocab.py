"""
User vocabulary with full SRS (SM-2) fields.
One row per (user, language, lemma) — language-isolated by design.
"""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import (
    String, Integer, Float, Text, DateTime, Boolean,
    ForeignKey, UniqueConstraint, func, Index,
)
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class UserVocab(Base):
    __tablename__ = "user_vocab"

    id:          Mapped[int]           = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id:     Mapped[int]           = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    lang_code:   Mapped[str]           = mapped_column(String(5),   nullable=False)  # 'fr' / 'de'

    # Word identity
    word:        Mapped[str]           = mapped_column(String(120), nullable=False)  # surface form
    lemma:       Mapped[str]           = mapped_column(String(120), nullable=False)  # canonical form
    pos:         Mapped[str]           = mapped_column(String(20),  default="Noun")  # NOUN/VERB/ADJ/ADV
    cefr:        Mapped[str]           = mapped_column(String(2),   default="B1")    # A1-C1
    frequency_zipf: Mapped[float]      = mapped_column(Float,       default=0.0)

    # Enrichment
    translation: Mapped[str | None]    = mapped_column(String(300), nullable=True)
    ipa:         Mapped[str | None]    = mapped_column(String(150), nullable=True)
    definition:  Mapped[str | None]    = mapped_column(Text,        nullable=True)
    example:     Mapped[str | None]    = mapped_column(Text,        nullable=True)
    audio_url:   Mapped[str | None]    = mapped_column(String(500), nullable=True)

    # Source context — links word back to the movie or book it came from
    source_movie:     Mapped[str | None] = mapped_column(String(200), nullable=True)
    source_book:      Mapped[str | None] = mapped_column(String(300), nullable=True)
    movie_id:         Mapped[int | None] = mapped_column(ForeignKey("movies.id",       ondelete="SET NULL"), nullable=True, index=True)
    book_id:          Mapped[int | None] = mapped_column(ForeignKey("book_library.id", ondelete="SET NULL"), nullable=True, index=True)
    context_sentence: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── SM-2 Spaced Repetition ────────────────────────────────────────────────
    status:      Mapped[str]           = mapped_column(String(20),  default="new")
    # new → learning → review → mastered → known
    ease_factor: Mapped[float]         = mapped_column(Float,       default=2.5)
    interval_days: Mapped[float]       = mapped_column(Float,       default=1.0)
    next_review: Mapped[datetime | None] = mapped_column(DateTime,  nullable=True)
    review_count: Mapped[int]          = mapped_column(Integer,     default=0)
    correct_count: Mapped[int]         = mapped_column(Integer,     default=0)
    lapse_count:  Mapped[int]          = mapped_column(Integer,     default=0)
    mastery_score: Mapped[float]       = mapped_column(Float,       default=0.0)  # 0.0-1.0
    consecutive_correct: Mapped[int]   = mapped_column(Integer,     default=0)

    # Timestamps
    first_seen:   Mapped[datetime]     = mapped_column(DateTime, default=func.now())
    last_reviewed: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("user_id", "lang_code", "lemma", name="uq_user_lang_lemma"),
        Index("ix_user_vocab_review_queue", "user_id", "lang_code", "next_review", "status"),
    )
