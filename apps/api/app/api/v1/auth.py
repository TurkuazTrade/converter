from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.api.v1.deps import get_identity_claims
from app.core.config import settings
from app.core.security import create_access_token, verify_password
from app.db.session import get_db
from app.models.user import User
from app.repositories.users import UserRepository
from app.schemas.auth import CurrentUserResponse, LoginRequest, TokenResponse

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Annotated[Session, Depends(get_db)]) -> TokenResponse:
    user = UserRepository(db).get_by_email(_login_email(payload.email))
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")
    return TokenResponse(access_token=create_access_token(str(user.id)))


def _login_email(login: str) -> str:
    value = login.strip()
    if value.casefold() == settings.default_test_user_login.casefold():
        return settings.default_test_user_email
    return value


@router.get("/me", response_model=CurrentUserResponse)
def me(
    current_user: Annotated[User, Depends(get_current_user)],
    claims: Annotated[dict[str, object], Depends(get_identity_claims)],
) -> CurrentUserResponse:
    roles = claims.get("roles")
    role = current_user.role
    if isinstance(roles, list) and roles:
        role = str(roles[0])
    return CurrentUserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=role,
    )
