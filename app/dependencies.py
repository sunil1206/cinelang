"""FastAPI dependency injection — database session + current user resolution."""
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.core.exceptions import AuthError
from app.database import get_db
from app.models.user import User

_bearer = HTTPBearer(auto_error=True)
_bearer_optional = HTTPBearer(auto_error=False)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _resolve_user(token: str, db: Session) -> User:
    try:
        payload = decode_token(token, "access")
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise AuthError("Invalid or expired access token")

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise AuthError("User not found or deactivated")
    return user


# ── Public dependencies ───────────────────────────────────────────────────────

def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
    db:          Annotated[Session, Depends(get_db)],
) -> User:
    """Requires a valid Bearer access token.  Raises 401 on failure."""
    return _resolve_user(credentials.credentials, db)


def get_optional_user(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(_bearer_optional)],
    db:          Annotated[Session, Depends(get_db)],
) -> Optional[User]:
    """Resolves the user if a token is present; returns None otherwise."""
    if credentials is None:
        return None
    try:
        return _resolve_user(credentials.credentials, db)
    except AuthError:
        return None


# ── Convenience type aliases (use in router signatures) ───────────────────────

CurrentUser         = Annotated[User,          Depends(get_current_user)]
OptionalCurrentUser = Annotated[Optional[User], Depends(get_optional_user)]
DBSession           = Annotated[Session,        Depends(get_db)]
