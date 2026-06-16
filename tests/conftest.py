"""pytest fixtures — in-memory SQLite database + TestClient."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import create_app
from app.database import get_db
from app.models.base import Base
import app.models.user        # noqa: F401 — register models
import app.models.vocabulary  # noqa: F401


@pytest.fixture(scope="session")
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture
def db_session(db_engine):
    connection = db_engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    application = create_app()
    application.dependency_overrides[get_db] = lambda: db_session

    with TestClient(application) as c:
        yield c


@pytest.fixture
def test_user(db_session):
    from app.models.user import User
    user = User(
        google_id="test-google-id-123",
        email="test@example.com",
        name="Test User",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user):
    from app.core.security import create_token
    token, _ = create_token(test_user.id, "access")
    return {"Authorization": f"Bearer {token}"}
