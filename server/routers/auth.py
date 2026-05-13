from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from server.auth import CurrentUser, authenticate_user, create_user_access_token, hash_password
from server.db import get_db, seed_default_portfolio
from server.models import User
from server.schemas import LoginRequest, RegisterRequest, TokenResponse, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])

DbSession = Annotated[Session, Depends(get_db)]


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: DbSession):
    user = authenticate_user(db, payload.email, payload.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="邮箱或密码不正确")
    return TokenResponse(access_token=create_user_access_token(user), user=UserRead.model_validate(user))


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: DbSession):
    normalized_email = payload.email.lower().strip()
    existing = db.scalars(select(User).where(User.email == normalized_email).limit(1)).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="邮箱已注册")

    user = User(
        email=normalized_email,
        name=(payload.name or normalized_email.split("@", 1)[0]).strip() or normalized_email,
        password_hash=hash_password(payload.password),
        is_active=True,
    )
    db.add(user)
    db.flush()
    seed_default_portfolio(user.id, db=db)
    db.commit()
    db.refresh(user)
    return TokenResponse(access_token=create_user_access_token(user), user=UserRead.model_validate(user))


@router.get("/me", response_model=UserRead)
def me(current_user: CurrentUser):
    return current_user
