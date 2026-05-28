from __future__ import annotations

from typing import Annotated

import httpx
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
    if settings.identity_api_url:
        return _login_with_identity(payload)

    user = UserRepository(db).get_by_email(_login_email(payload.email))
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")
    return TokenResponse(access_token=create_access_token(str(user.id)))


def _login_with_identity(payload: LoginRequest) -> TokenResponse:
    login_url = f"{settings.identity_api_url.rstrip('/')}/auth/login"
    try:
        response = httpx.post(
            login_url,
            json={"email": _login_email(payload.email), "password": payload.password},
            timeout=10.0,
        )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Identity service is unavailable",
        ) from exc

    if response.status_code in {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN}:
        detail = _response_detail(response) or "Incorrect email or password"
        raise HTTPException(status_code=response.status_code, detail=detail)
    if response.status_code >= 400:
        detail = _response_detail(response) or "Identity service rejected login"
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail)

    data = response.json()
    access_token = data.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Identity service returned an invalid token response",
        )
    token_type = data.get("token_type")
    return TokenResponse(
        access_token=access_token,
        token_type=token_type if isinstance(token_type, str) and token_type else "bearer",
    )


def _response_detail(response: httpx.Response) -> str | None:
    try:
        detail = response.json().get("detail")
    except ValueError:
        return None
    return detail if isinstance(detail, str) and detail else None


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
