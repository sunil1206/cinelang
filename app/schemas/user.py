from datetime import datetime
from pydantic import BaseModel


class UserOut(BaseModel):
    id:         int
    email:      str
    name:       str
    picture:    str | None = None
    is_active:  bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    name:    str | None = None
    picture: str | None = None
