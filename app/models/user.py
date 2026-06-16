from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id:            Mapped[int]       = mapped_column(primary_key=True, index=True)
    google_id:     Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True, index=True)
    email:         Mapped[str]       = mapped_column(String(255), nullable=False, index=True, unique=True)
    name:          Mapped[str]       = mapped_column(String(255), nullable=False)
    picture:       Mapped[str | None] = mapped_column(String(512))
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active:     Mapped[bool]      = mapped_column(Boolean, default=True, nullable=False)

    vocab = relationship(
        "VocabEntry",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r}>"
