"""BookLibrary — one row per uploaded/pasted book, acts as a vocabulary folder."""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, func, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class BookLibrary(Base):
    __tablename__ = "book_library"

    id:           Mapped[int]       = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id:      Mapped[int]       = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    title:        Mapped[str]       = mapped_column(String(300), nullable=False)
    author:       Mapped[str]       = mapped_column(String(200), default="")
    lang_code:    Mapped[str]       = mapped_column(String(5),   nullable=False, default="fr")
    target_lang:  Mapped[str]       = mapped_column(String(5),   nullable=False, default="en")

    total_words:  Mapped[int]       = mapped_column(Integer, default=0)
    unique_words: Mapped[int]       = mapped_column(Integer, default=0)
    saved_count:  Mapped[int]       = mapped_column(Integer, default=0)
    cefr_json:    Mapped[str]       = mapped_column(Text, default="{}")    # JSON {"A1":n,...}

    created_at:   Mapped[datetime]  = mapped_column(DateTime, default=func.now())

    vocab_entries = relationship(
        "VocabEntry",
        primaryjoin="BookLibrary.id == foreign(VocabEntry.book_id)",
        lazy="dynamic",
    )

    __table_args__ = (
        Index("ix_book_library_user", "user_id"),
    )
