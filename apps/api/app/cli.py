from __future__ import annotations

import argparse

from app.db.session import SessionLocal
from app.repositories.users import UserRepository


def create_admin(email: str, password: str, full_name: str) -> None:
    with SessionLocal() as db:
        repo = UserRepository(db)
        if repo.get_by_email(email):
            print(f"Admin already exists: {email}")
            return
        repo.create_admin(email=email, password=password, full_name=full_name)
        db.commit()
        print(f"Admin created: {email}")


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_admin_parser = subparsers.add_parser("create-admin")
    create_admin_parser.add_argument("--email", required=True)
    create_admin_parser.add_argument("--password", required=True)
    create_admin_parser.add_argument("--full-name", default="Admin")

    args = parser.parse_args()
    if args.command == "create-admin":
        create_admin(args.email, args.password, args.full_name)


if __name__ == "__main__":
    main()
