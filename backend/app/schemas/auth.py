import uuid

from pydantic import BaseModel, EmailStr

from app.models.team_member import TeamRole


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class CurrentUser(BaseModel):
    id: uuid.UUID
    shop_id: uuid.UUID
    email: EmailStr
    role: TeamRole

    model_config = {"from_attributes": True}
