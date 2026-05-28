from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User
from app.repositories.users import UserRepository

bearer_scheme = HTTPBearer(auto_error=False)


def get_identity_claims(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> dict[str, Any]:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        return jwt.decode(
            credentials.credentials,
            settings.identity_secret_key,
            algorithms=[settings.identity_algorithm],
        )
    except jwt.PyJWTError:
        if settings.environment != "development":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    try:
        claims = decode_access_token(credentials.credentials)
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc
    claims.setdefault(
        "permissions",
        [
            "converter.clients.read",
            "converter.files.read",
            "converter.orders.read",
            "converter.products.read",
            "converter.references.read",
        ],
    )
    return claims


def get_current_user(
    claims: Annotated[dict[str, Any], Depends(get_identity_claims)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    subject = claims.get("sub")
    if subject is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    try:
        user_id = int(subject)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    repo = UserRepository(db)
    user = repo.get(user_id)
    if user is None:
        user = _create_shadow_user(db, user_id=user_id, claims=claims)
    elif user.deleted_at is not None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
    return user


def require_permission(permission: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
    def dependency(claims: Annotated[dict[str, Any], Depends(get_identity_claims)]) -> dict[str, Any]:
        if _has_permission(claims, permission):
            return claims
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Missing permission: {permission}",
        )

    return dependency


def _has_permission(claims: dict[str, Any], permission: str) -> bool:
    permissions = claims.get("permissions")
    if isinstance(permissions, list) and permission in permissions:
        return True
    branch_permissions = claims.get("branch_permissions")
    if isinstance(branch_permissions, dict):
        return any(
            isinstance(values, list) and permission in values
            for values in branch_permissions.values()
        )
    return False


def _create_shadow_user(db: Session, *, user_id: int, claims: dict[str, Any]) -> User:
    email = claims.get("email")
    full_name = claims.get("full_name")
    if not isinstance(email, str) or not email:
        email = f"identity-{user_id}@local.invalid"
    email = email.casefold()
    if not isinstance(full_name, str) or not full_name:
        full_name = email
    roles = claims.get("roles")
    role = "admin" if isinstance(roles, list) and "platform_admin" in roles else "operator"
    existing = UserRepository(db).get_by_email(email)
    if existing is not None:
        existing.full_name = full_name
        existing.role = role
        existing.is_active = True
        db.commit()
        db.refresh(existing)
        return existing
    user = User(
        id=user_id,
        email=email,
        hashed_password="identity-managed",
        full_name=full_name,
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
