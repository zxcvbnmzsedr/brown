from __future__ import annotations

import argparse
import getpass

from sqlalchemy import select

from backend.auth import hash_password
from backend.db import SessionLocal, init_db, seed_permanent_portfolio
from backend.models import User


def create_user(email: str, name: str | None, password: str | None) -> None:
    normalized_email = email.lower().strip()
    password_value = password or getpass.getpass("Password: ")
    if not password_value:
        raise SystemExit("Password is required")

    init_db()
    with SessionLocal() as db:
        existing = db.scalars(select(User).where(User.email == normalized_email).limit(1)).first()
        if existing:
            existing.name = name or existing.name
            existing.password_hash = hash_password(password_value)
            existing.is_active = True
            user = existing
            action = "updated"
        else:
            user = User(
                email=normalized_email,
                name=name or normalized_email.split("@", 1)[0],
                password_hash=hash_password(password_value),
                is_active=True,
            )
            db.add(user)
            db.flush()
            action = "created"

        seed_permanent_portfolio(user.id, db=db)
        db.commit()
        print(f"User {action}: {user.email}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Brown backend management")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init-db")
    init_parser.set_defaults(func=lambda _args: init_db())

    user_parser = subparsers.add_parser("create-user")
    user_parser.add_argument("--email", required=True)
    user_parser.add_argument("--name")
    user_parser.add_argument("--password")
    user_parser.set_defaults(func=lambda args: create_user(args.email, args.name, args.password))

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
