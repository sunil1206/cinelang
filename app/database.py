from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from app.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},  # SQLite only
    pool_pre_ping=True,
)

# Enable WAL mode and foreign keys for SQLite
@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_conn, _record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:  # type: ignore[return]
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables() -> None:
    from app.models.base import Base  # noqa: F401 — imports all models
    import app.models.user              # noqa: F401
    import app.models.vocabulary        # noqa: F401
    import app.models.language_profile  # noqa: F401
    import app.models.user_vocab        # noqa: F401
    import app.models.deck              # noqa: F401
    import app.models.review            # noqa: F401
    import app.models.book              # noqa: F401
    import app.models.movie             # noqa: F401
    Base.metadata.create_all(bind=engine)
