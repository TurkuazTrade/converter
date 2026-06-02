from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import DEFAULT_BRANCH_NAME
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.branch import Branch
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
    if _sync_user_branch(db, user, claims):
        db.commit()
        db.refresh(user)
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

    branch_id, _branch_name, branch_code = _branch_claim(claims)

    branch_permissions_by_id = claims.get("branch_permissions_by_id")
    if isinstance(branch_permissions_by_id, dict) and branch_id is not None:
        for key in (branch_id, str(branch_id)):
            values = branch_permissions_by_id.get(key)
            if isinstance(values, list) and permission in values:
                return True

    branch_permissions = claims.get("branch_permissions")
    if isinstance(branch_permissions, dict):
        scope_keys: list[object] = []
        if branch_code is not None:
            scope_keys.append(branch_code)
        if branch_id is not None:
            scope_keys.extend([branch_id, str(branch_id)])
        for key in scope_keys:
            values = branch_permissions.get(key)
            if isinstance(values, list) and permission in values:
                return True
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


def _sync_user_branch(db: Session, user: User, claims: dict[str, Any]) -> bool:
    branch_id, branch_name, branch_code = _branch_claim(claims)
    if branch_id is None:
        return False

    changed = False
    branch = db.get(Branch, branch_id)
    if branch is None:
        branch = Branch(
            id=branch_id,
            name=branch_name or f"{DEFAULT_BRANCH_NAME} {branch_id}",
            code=branch_code,
            is_active=True,
        )
        db.add(branch)
        changed = True
    else:
        if branch_name and branch.name != branch_name:
            branch.name = branch_name
            changed = True
        if branch_code and branch.code != branch_code:
            branch.code = branch_code
            changed = True
        if not branch.is_active:
            branch.is_active = True
            changed = True

    if user.branch_id != branch_id:
        user.branch_id = branch_id
        changed = True
    return changed


def _branch_claim(claims: dict[str, Any]) -> tuple[int | None, str | None, str | None]:
    branch_payload = claims.get("branch")
    branch_name = _string_claim(claims.get("branch_name") or claims.get("branchName"))
    branch_code = _string_claim(claims.get("branch_code") or claims.get("branchCode"))
    branch_id = None

    if isinstance(branch_payload, dict):
        branch_id = _int_claim(
            branch_payload.get("id")
            or branch_payload.get("branch_id")
            or branch_payload.get("branchId")
        )
        branch_name = _string_claim(branch_payload.get("name")) or branch_name
        branch_code = _string_claim(branch_payload.get("code")) or branch_code

    for key in (
        "branch_id",
        "branchId",
        "active_branch_id",
        "activeBranchId",
        "current_branch_id",
        "currentBranchId",
        "selected_branch_id",
        "selectedBranchId",
    ):
        branch_id = branch_id or _int_claim(claims.get(key))

    if branch_id is None:
        branch_permissions_by_id = claims.get("branch_permissions_by_id")
        if isinstance(branch_permissions_by_id, dict) and len(branch_permissions_by_id) == 1:
            branch_id = _int_claim(next(iter(branch_permissions_by_id.keys())))

    if branch_id is None:
        branch_permissions = claims.get("branch_permissions")
        if isinstance(branch_permissions, dict) and len(branch_permissions) == 1:
            branch_id = _int_claim(next(iter(branch_permissions.keys())))

    return branch_id, branch_name, branch_code


def _int_claim(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _string_claim(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None
