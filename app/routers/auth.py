"""Authentication router — Google OAuth + JWT refresh."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import CurrentUser, DBSession
from app.schemas.auth import AuthResponse, GoogleAuthRequest, LoginRequest, RefreshRequest, RegisterRequest
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=AuthResponse, summary="Register with email + password")
def register(body: RegisterRequest, db: DBSession):
    return auth_service.register_user(db, body)


@router.post("/login", response_model=AuthResponse, summary="Login with email + password")
def login(body: LoginRequest, db: DBSession):
    return auth_service.login_user(db, body)


@router.post(
    "/google",
    response_model=AuthResponse,
    summary="Exchange a Google id_token for CineLang access + refresh tokens",
)
async def google_sign_in(body: GoogleAuthRequest, db: DBSession):
    """
    The Next.js frontend calls this after a successful Google sign-in.
    The id_token comes from NextAuth's jwt callback (account.id_token).

    1. Verify the id_token with Google's tokeninfo endpoint.
    2. Create or update the User row.
    3. Issue an access token (24 h) and a refresh token (30 d).
    """
    claims = await auth_service.verify_google_id_token(body.id_token)
    user   = auth_service.get_or_create_user(db, claims)
    return auth_service.issue_auth_response(user)


@router.post(
    "/refresh",
    response_model=AuthResponse,
    summary="Exchange a refresh token for a new access token",
)
def refresh(body: RefreshRequest, db: DBSession):
    return auth_service.refresh_access_token(db, body.refresh_token)


@router.get(
    "/me",
    response_model=AuthResponse,
    summary="Return current user info (validates access token)",
)
def me(current_user: CurrentUser, db: DBSession):
    return auth_service.issue_auth_response(current_user)
