from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from server.auth import CurrentUser
from server.db import get_db
from server.models import Instrument, InvestmentAccount, Portfolio, PortfolioGroup, UserAsset
from server.schemas import UserAssetCreate, UserAssetRead, UserAssetUpdate
from server.services.portfolio import position_totals, user_asset_read

router = APIRouter(prefix="/user-assets", tags=["user-assets"])

DbSession = Annotated[Session, Depends(get_db)]


def validate_user_asset_payload(db: Session, user_id: int, payload: UserAssetCreate | UserAssetUpdate) -> None:
    portfolio = db.scalars(select(Portfolio.id).where(Portfolio.user_id == user_id, Portfolio.id == payload.portfolio_id).limit(1)).first()
    if portfolio is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")
    instrument = db.get(Instrument, payload.instrument_id)
    if instrument is None or not instrument.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instrument not found")
    if payload.portfolio_group_id is not None:
        group = db.scalars(
            select(PortfolioGroup)
            .where(
                PortfolioGroup.user_id == user_id,
                PortfolioGroup.portfolio_id == payload.portfolio_id,
                PortfolioGroup.id == payload.portfolio_group_id,
            )
            .limit(1)
        ).first()
        if group is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio group not found")
    if payload.account_id is not None:
        account = db.scalars(
            select(InvestmentAccount)
            .where(
                InvestmentAccount.user_id == user_id,
                InvestmentAccount.portfolio_id == payload.portfolio_id,
                InvestmentAccount.id == payload.account_id,
            )
            .limit(1)
        ).first()
        if account is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investment account not found")


def get_user_asset_or_404(db: Session, user_id: int, asset_id: int) -> UserAsset:
    asset = db.scalars(
        select(UserAsset)
        .options(
            selectinload(UserAsset.instrument),
            selectinload(UserAsset.group).selectinload(PortfolioGroup.bucket),
            selectinload(UserAsset.account),
        )
        .where(UserAsset.user_id == user_id, UserAsset.id == asset_id)
        .limit(1)
    ).first()
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User asset not found")
    return asset


@router.get("", response_model=list[UserAssetRead])
def list_user_assets(db: DbSession, current_user: CurrentUser, portfolio_id: int):
    totals = position_totals(db, current_user.id, portfolio_id)
    assets = db.scalars(
        select(UserAsset)
        .options(
            selectinload(UserAsset.instrument),
            selectinload(UserAsset.group).selectinload(PortfolioGroup.bucket),
            selectinload(UserAsset.account),
        )
        .where(UserAsset.user_id == current_user.id, UserAsset.portfolio_id == portfolio_id)
        .order_by(UserAsset.id)
    ).all()
    return [
        user_asset_read(db, asset, *totals.get(asset.instrument_id, (0.0, 0.0)))
        for asset in assets
    ]


@router.post("", response_model=UserAssetRead, status_code=status.HTTP_201_CREATED)
def create_user_asset(payload: UserAssetCreate, db: DbSession, current_user: CurrentUser):
    validate_user_asset_payload(db, current_user.id, payload)
    existing = db.scalars(
        select(UserAsset)
        .where(
            UserAsset.user_id == current_user.id,
            UserAsset.portfolio_id == payload.portfolio_id,
            UserAsset.instrument_id == payload.instrument_id,
        )
        .limit(1)
    ).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User asset already exists")
    asset = UserAsset(user_id=current_user.id, **payload.model_dump())
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return user_asset_read(db, get_user_asset_or_404(db, current_user.id, asset.id))


@router.put("/{asset_id}", response_model=UserAssetRead)
def update_user_asset(asset_id: int, payload: UserAssetUpdate, db: DbSession, current_user: CurrentUser):
    validate_user_asset_payload(db, current_user.id, payload)
    asset = get_user_asset_or_404(db, current_user.id, asset_id)
    for key, value in payload.model_dump().items():
        setattr(asset, key, value)
    db.commit()
    db.refresh(asset)
    return user_asset_read(db, get_user_asset_or_404(db, current_user.id, asset.id))


@router.post("/{asset_id}/toggle", response_model=UserAssetRead)
def toggle_user_asset(asset_id: int, db: DbSession, current_user: CurrentUser):
    asset = get_user_asset_or_404(db, current_user.id, asset_id)
    asset.is_active = not asset.is_active
    db.commit()
    db.refresh(asset)
    return user_asset_read(db, get_user_asset_or_404(db, current_user.id, asset.id))
