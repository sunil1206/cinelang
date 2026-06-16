from pydantic import BaseModel, EmailStr, field_validator


# ── Requests ──────────────────────────────────────────────────────────────────

class GoogleAuthRequest(BaseModel):
    id_token: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


# ── Responses ─────────────────────────────────────────────────────────────────

class TokenPair(BaseModel):
    access_token:  str
    refresh_token: str
    token_type:    str = "bearer"
    expires_in:    int          # seconds until access_token expires


class UserOut(BaseModel):
    id:       int
    email:    str
    name:     str
    picture:  str | None = None

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    tokens: TokenPair
    user:   UserOut
