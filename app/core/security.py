"""JWT creation and validation — all token logic lives here."""
from datetime import datetime, timedelta, timezone
from typing import Literal

from jose import JWTError, jwt

from app.config import get_settings

settings = get_settings()

TokenKind = Literal["access", "refresh"]

# Separate secrets so a stolen refresh token can't be used as an access token
_ACCESS_SECRET  = settings.jwt_secret + ":access"
_REFRESH_SECRET = settings.jwt_secret + ":refresh"


def _secret(kind: TokenKind) -> str:
    return _ACCESS_SECRET if kind == "access" else _REFRESH_SECRET


def create_token(user_id: int, kind: TokenKind) -> tuple[str, int]:
    """Return (encoded_jwt, expires_in_seconds)."""
    if kind == "access":
        delta = timedelta(minutes=settings.access_token_expire_minutes)
    else:
        delta = timedelta(days=settings.refresh_token_expire_days)

    now     = datetime.now(timezone.utc)
    expires = now + delta
    payload = {
        "sub":  str(user_id),
        "kind": kind,
        "iat":  now,
        "exp":  expires,
    }
    token = jwt.encode(payload, _secret(kind), algorithm=settings.jwt_algorithm)
    return token, int(delta.total_seconds())


def decode_token(token: str, kind: TokenKind) -> dict:
    """Decode and validate a JWT.  Raises JWTError on any failure."""
    payload = jwt.decode(token, _secret(kind), algorithms=[settings.jwt_algorithm])
    if payload.get("kind") != kind:
        raise JWTError("Token kind mismatch")
    return payload


def create_token_pair(user_id: int) -> tuple[str, str, int]:
    """Return (access_token, refresh_token, access_expires_in)."""
    access,  expires = create_token(user_id, "access")
    refresh, _       = create_token(user_id, "refresh")
    return access, refresh, expires
