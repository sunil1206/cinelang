import json
from sqlalchemy import String, Integer, Text, UniqueConstraint, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin


class Movie(Base, TimestampMixin):
    __tablename__ = "movies"
    __table_args__ = (
        UniqueConstraint("user_id", "title", "language", name="uq_user_movie_lang"),
    )

    id:             Mapped[int]       = mapped_column(primary_key=True, index=True)
    user_id:        Mapped[int]       = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title:          Mapped[str]       = mapped_column(String(256), nullable=False, index=True)
    year:           Mapped[int | None] = mapped_column(Integer)
    language:       Mapped[str]       = mapped_column(String(8), default="fr", nullable=False)
    subtitle_count: Mapped[int]       = mapped_column(Integer, default=0, nullable=False)

    # Vocabulary stats (populated when subtitles are analyzed)
    vocab_count:    Mapped[int]       = mapped_column(Integer, default=0, nullable=False)
    cefr_json:      Mapped[str]       = mapped_column(Text, default="{}")
    target_lang:    Mapped[str]       = mapped_column(String(8), default="en", nullable=False)

    vocab_links  = relationship("MovieVocab", back_populates="movie", cascade="all, delete-orphan")


class MovieVocab(Base):
    """Join table — movie ↔ vocabulary entry."""
    __tablename__ = "movie_vocab"

    id:          Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    movie_id:    Mapped[int] = mapped_column(ForeignKey("movies.id", ondelete="CASCADE"), nullable=False, index=True)
    vocab_id:    Mapped[int] = mapped_column(ForeignKey("vocabulary.id", ondelete="CASCADE"), nullable=False, index=True)

    movie       = relationship("Movie", back_populates="vocab_links")
    vocab_entry = relationship("VocabEntry", back_populates="movie_links")
