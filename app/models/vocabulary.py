from datetime import datetime
from sqlalchemy import String, Integer, Text, Float, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin


class VocabEntry(Base, TimestampMixin):
    __tablename__ = "vocabulary"
    __table_args__ = (
        UniqueConstraint("user_id", "word", "target_lang", name="uq_user_word_lang"),
    )

    id:          Mapped[int]       = mapped_column(primary_key=True, index=True)
    user_id:     Mapped[int]       = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    word:        Mapped[str]       = mapped_column(String(128), nullable=False, index=True)
    lemma:       Mapped[str | None] = mapped_column(String(128), index=True)
    source_lang: Mapped[str]       = mapped_column(String(8), default="en", nullable=False)
    target_lang: Mapped[str]       = mapped_column(String(8), default="fr", nullable=False)

    translation: Mapped[str | None] = mapped_column(String(512))
    pos:         Mapped[str | None] = mapped_column(String(32))
    phonetic:    Mapped[str | None] = mapped_column(String(128))
    explanation: Mapped[str | None] = mapped_column(Text)
    example_sentence:       Mapped[str | None] = mapped_column(Text)
    sentence_translation:   Mapped[str | None] = mapped_column(Text)

    # CEFR / frequency
    cefr_level:     Mapped[str | None] = mapped_column(String(4))   # A1 A2 B1 B2 C1
    frequency_rank: Mapped[str | None] = mapped_column(String(16))  # very common common uncommon rare

    # Learning state
    status:         Mapped[str]  = mapped_column(String(16), default="new", nullable=False)  # new|learning|mastered
    mastered:       Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    count:          Mapped[int]  = mapped_column(Integer, default=1, nullable=False)
    review_count:   Mapped[int]  = mapped_column(Integer, default=0, nullable=False)
    retention_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    learning_priority: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # SM-2 spaced repetition
    next_review:    Mapped[datetime | None] = mapped_column(DateTime)
    last_seen:      Mapped[datetime | None] = mapped_column(DateTime)

    # Book source
    book_id:     Mapped[int | None] = mapped_column(Integer, ForeignKey("book_library.id", ondelete="SET NULL"), nullable=True, index=True)
    source_book: Mapped[str | None] = mapped_column(String(300), nullable=True)

    # Movie/cinema source
    movie_id:    Mapped[int | None] = mapped_column(Integer, ForeignKey("movies.id", ondelete="SET NULL"), nullable=True, index=True)
    source_movie: Mapped[str | None] = mapped_column(String(300), nullable=True)

    # JSON-encoded lists stored as TEXT
    contexts:    Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    timestamps:  Mapped[str] = mapped_column(Text, default="[]", nullable=False)

    user         = relationship("User", back_populates="vocab")
    movie_links  = relationship("MovieVocab", back_populates="vocab_entry", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<VocabEntry id={self.id} word={self.word!r} cefr={self.cefr_level}>"
