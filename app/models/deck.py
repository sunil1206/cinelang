"""Smart learning decks — five types, language-isolated."""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base

DECK_TYPES = ("core", "movie", "expressions", "grammar", "review")


class Deck(Base):
    __tablename__ = "decks"

    id:          Mapped[int]  = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id:     Mapped[int]  = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    lang_code:   Mapped[str]  = mapped_column(String(5),   nullable=False)
    deck_type:   Mapped[str]  = mapped_column(String(20),  nullable=False)  # see DECK_TYPES
    name:        Mapped[str]  = mapped_column(String(200), nullable=False)
    description: Mapped[str]  = mapped_column(String(400), default="")
    movie_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    word_count:  Mapped[int]  = mapped_column(Integer, default=0)
    created_at:  Mapped[datetime] = mapped_column(DateTime, default=func.now())

    __table_args__ = (
        Index("ix_decks_user_lang", "user_id", "lang_code"),
    )


class DeckWord(Base):
    __tablename__ = "deck_words"

    id:            Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    deck_id:       Mapped[int] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"), nullable=False)
    user_vocab_id: Mapped[int] = mapped_column(ForeignKey("user_vocab.id", ondelete="CASCADE"), nullable=False)
    order_index:   Mapped[int] = mapped_column(Integer, default=0)
    added_at:      Mapped[datetime] = mapped_column(DateTime, default=func.now())

    __table_args__ = (
        Index("ix_deck_words_deck", "deck_id", "order_index"),
    )
