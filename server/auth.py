from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Literal

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from server.db import get_db, seed_default_portfolio
from server.models import User


JWT_ALGORITHM = "HS256"
PASSWORD_ITERATIONS = 260_000
user_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
admin_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/admin/auth/login")


def _user_jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET")
    if not secret:
        if os.getenv("ENVIRONMENT") == "production":
            raise RuntimeError("JWT_SECRET is required in production")
        return "brown-user-dev-secret-change-me"
    return secret


def _admin_jwt_secret() -> str:
    secret = os.getenv("ADMIN_JWT_SECRET")
    if not secret:
        if os.getenv("ENVIRONMENT") == "production":
            raise RuntimeError("ADMIN_JWT_SECRET is required in production")
        return "brown-admin-dev-secret-change-me"
    return secret


def admin_email() -> str:
    return os.getenv("ADMIN_EMAIL", "admin@example.com").lower().strip()


def admin_password() -> str:
    return os.getenv("ADMIN_PASSWORD", "admin123456")


def _access_token_minutes() -> int:
    raw = os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "10080")
    try:
        return max(int(raw), 1)
    except ValueError:
        return 10080


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${_b64url_encode(salt)}${_b64url_encode(digest)}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        scheme, iterations, salt_raw, digest_raw = password_hash.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        salt = _b64url_decode(salt_raw)
        expected = _b64url_decode(digest_raw)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def _create_token(payload: dict[str, Any], secret: str) -> str:
    header = {"alg": JWT_ALGORITHM, "typ": "JWT"}
    signing_input = ".".join(
        [
            _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8")),
            _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
        ]
    )
    signature = hmac.new(secret.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
    return f"{signing_input}.{_b64url_encode(signature)}"


def create_user_access_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    return _create_token(
        {
            "sub": str(user.id),
            "email": user.email,
            "kind": "user",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=_access_token_minutes())).timestamp()),
        },
        _user_jwt_secret(),
    )


def create_admin_access_token(email: str) -> str:
    now = datetime.now(timezone.utc)
    return _create_token(
        {
            "sub": email,
            "email": email,
            "kind": "admin",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=_access_token_minutes())).timestamp()),
        },
        _admin_jwt_secret(),
    )


def decode_access_token(token: str, *, secret: str, expected_kind: Literal["user", "admin"]) -> dict[str, Any]:
    try:
        header_raw, payload_raw, signature_raw = token.split(".", 2)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    signing_input = f"{header_raw}.{payload_raw}"
    expected = hmac.new(secret.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
    try:
        supplied = _b64url_decode(signature_raw)
        payload = json.loads(_b64url_decode(payload_raw))
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    if not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    if payload.get("kind") != expected_kind:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token kind")

    exp = payload.get("exp")
    if not isinstance(exp, int) or datetime.now(timezone.utc).timestamp() >= exp:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    return payload


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = db.scalars(select(User).where(User.email == email.lower().strip()).limit(1)).first()
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def authenticate_admin(email: str, password: str) -> bool:
    return hmac.compare_digest(email.lower().strip(), admin_email()) and hmac.compare_digest(password, admin_password())


def get_current_user(token: Annotated[str, Depends(user_oauth2_scheme)], db: Annotated[Session, Depends(get_db)]) -> User:
    payload = decode_access_token(token, secret=_user_jwt_secret(), expected_kind="user")
    raw_user_id = payload.get("sub")
    try:
        user_id = int(raw_user_id)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    seed_default_portfolio(user.id, db=db)
    db.commit()
    return user


def get_current_admin(token: Annotated[str, Depends(admin_oauth2_scheme)]) -> str:
    payload = decode_access_token(token, secret=_admin_jwt_secret(), expected_kind="admin")
    email = str(payload.get("email") or "")
    if email != admin_email():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin not found")
    return email


CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentAdmin = Annotated[str, Depends(get_current_admin)]
