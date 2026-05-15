from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.user import User


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_email(self, email: str) -> User | None:
        return self.db.scalar(
            select(User).where(User.email == email, User.deleted_at.is_(None))
        )

    def get(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)

    def create_admin(self, email: str, password: str, full_name: str = "Admin") -> User:
        user = User(
            email=email,
            hashed_password=get_password_hash(password),
            full_name=full_name,
            role="admin",
            is_active=True,
        )
        self.db.add(user)
        self.db.flush()
        return user

    def ensure_user(self, email: str, password: str, full_name: str, role: str = "admin") -> User:
        user = self.get_by_email(email)
        hashed_password = get_password_hash(password)
        if user is None:
            user = User(
                email=email,
                hashed_password=hashed_password,
                full_name=full_name,
                role=role,
                is_active=True,
            )
            self.db.add(user)
            self.db.flush()
            return user

        user.hashed_password = hashed_password
        user.full_name = full_name
        user.role = role
        user.is_active = True
        self.db.flush()
        return user
