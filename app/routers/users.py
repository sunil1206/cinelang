"""User profile router."""
from fastapi import APIRouter

from app.dependencies import CurrentUser, DBSession
from app.schemas.user import UserOut, UserUpdate

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserOut, summary="Get the authenticated user's profile")
def get_me(current_user: CurrentUser):
    return current_user


@router.patch("/me", response_model=UserOut, summary="Update name or picture")
def update_me(body: UserUpdate, current_user: CurrentUser, db: DBSession):
    if body.name is not None:
        current_user.name = body.name
    if body.picture is not None:
        current_user.picture = body.picture
    db.commit()
    db.refresh(current_user)
    return current_user
