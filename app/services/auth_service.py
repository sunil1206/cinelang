"""Google token verification + user upsert + JWT issuance."""
import hashlib
import hmac
import os

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.exceptions import AuthError
from app.core.security import create_token_pair
from app.models.user import User
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest, TokenPair, UserOut

settings = get_settings()

_GOOGLE_TOKENINFO = "https://oauth2.googleapis.com/tokeninfo"


# ── Google verification ───────────────────────────────────────────────────────

async def verify_google_id_token(id_token: str) -> dict:
    """Call Google's tokeninfo endpoint and return the token claims."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(_GOOGLE_TOKENINFO, params={"id_token": id_token})

    if r.status_code != 200:
        raise AuthError("Google token verification failed")

    claims = r.json()

    # Validate audience if GOOGLE_CLIENT_ID is configured
    if settings.google_client_id and claims.get("aud") != settings.google_client_id:
        raise AuthError("Token audience does not match this application")

    google_id = claims.get("sub")
    if not google_id:
        raise AuthError("Token missing subject claim")

    return claims


# ── User upsert ───────────────────────────────────────────────────────────────

def get_or_create_user(db: Session, claims: dict) -> User:
    """Find the user by google_id; create them if they don't exist yet."""
    google_id = claims["sub"]
    user = db.query(User).filter(User.google_id == google_id).first()

    if user is None:
        user = User(
            google_id=google_id,
            email=claims.get("email", ""),
            name=claims.get("name", ""),
            picture=claims.get("picture"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        # Keep name / picture fresh
        changed = False
        if claims.get("name") and user.name != claims["name"]:
            user.name = claims["name"]
            changed = True
        if claims.get("picture") and user.picture != claims.get("picture"):
            user.picture = claims["picture"]
            changed = True
        if changed:
            db.commit()
            db.refresh(user)

    return user


# ── Token issuance ────────────────────────────────────────────────────────────

def issue_auth_response(user: User) -> AuthResponse:
    access, refresh, expires_in = create_token_pair(user.id)
    return AuthResponse(
        tokens=TokenPair(
            access_token=access,
            refresh_token=refresh,
            expires_in=expires_in,
        ),
        user=UserOut.model_validate(user),
    )


# ── Password helpers ─────────────────────────────────────────────────────────

def _hash_password(password: str) -> str:
    salt = os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260_000)
    return f"{salt}${digest.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt, digest_hex = stored.split("$", 1)
    except ValueError:
        return False
    expected = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260_000)
    return hmac.compare_digest(expected.hex(), digest_hex)


# ── Email/password auth ───────────────────────────────────────────────────────

def register_user(db: Session, body: RegisterRequest) -> AuthResponse:
    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        raise AuthError("Email already registered")

    user = User(
        email=body.email,
        name=body.name,
        password_hash=_hash_password(body.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return issue_auth_response(user)


def login_user(db: Session, body: LoginRequest) -> AuthResponse:
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not user.password_hash:
        raise AuthError("Invalid email or password")
    if not _verify_password(body.password, user.password_hash):
        raise AuthError("Invalid email or password")
    if not user.is_active:
        raise AuthError("Account is deactivated")
    return issue_auth_response(user)


# ── Token refresh ─────────────────────────────────────────────────────────────

def refresh_access_token(db: Session, refresh_token: str) -> AuthResponse:
    from jose import JWTError
    from app.core.security import decode_token

    try:
        payload = decode_token(refresh_token, "refresh")
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise AuthError("Invalid or expired refresh token")

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise AuthError("User not found or deactivated")

    return issue_auth_response(user)
