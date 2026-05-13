from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from server.auth import CurrentUser
from server.db import get_db
from server.models import CashAccount, InvestmentAccount, Portfolio, TradingPlatform
from server.schemas import (
    CashAccountCreate,
    CashAccountRead,
    CashAccountUpdate,
    InvestmentAccountCreate,
    InvestmentAccountRead,
)

router = APIRouter(tags=["accounts"])

DbSession = Annotated[Session, Depends(get_db)]


def ensure_portfolio(db: Session, user_id: int, portfolio_id: int) -> None:
    exists = db.scalars(select(Portfolio.id).where(Portfolio.user_id == user_id, Portfolio.id == portfolio_id).limit(1)).first()
    if exists is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")


def platform_or_404(db: Session, platform_id: int) -> TradingPlatform:
    platform = db.get(TradingPlatform, platform_id)
    if platform is None or not platform.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trading platform not found")
    return platform


def investment_account_response(account: InvestmentAccount) -> InvestmentAccountRead:
    return InvestmentAccountRead(
        id=account.id,
        portfolio_id=account.portfolio_id,
        trading_platform_id=account.trading_platform_id,
        name=account.name,
        is_active=account.is_active,
        platform_name=account.platform.name if account.platform else None,
        platform_type=account.platform.type if account.platform else None,
    )


def cash_account_response(account: CashAccount) -> CashAccountRead:
    return CashAccountRead(
        id=account.id,
        portfolio_id=account.portfolio_id,
        trading_platform_id=account.trading_platform_id,
        name=account.name,
        currency=account.currency,
        balance=account.balance,
        balance_date=account.balance_date,
        include_in_rebalance=account.include_in_rebalance,
        is_active=account.is_active,
        platform_name=account.platform.name if account.platform else None,
    )


@router.get("/investment-accounts", response_model=list[InvestmentAccountRead])
def list_investment_accounts(db: DbSession, current_user: CurrentUser, portfolio_id: int | None = None):
    statement = (
        select(InvestmentAccount)
        .options(selectinload(InvestmentAccount.platform))
        .where(InvestmentAccount.user_id == current_user.id)
    )
    if portfolio_id is not None:
        statement = statement.where(InvestmentAccount.portfolio_id == portfolio_id)
    accounts = db.scalars(statement.order_by(InvestmentAccount.id)).all()
    return [investment_account_response(account) for account in accounts]


@router.post("/investment-accounts", response_model=InvestmentAccountRead, status_code=status.HTTP_201_CREATED)
def create_investment_account(payload: InvestmentAccountCreate, db: DbSession, current_user: CurrentUser):
    ensure_portfolio(db, current_user.id, payload.portfolio_id)
    platform_or_404(db, payload.trading_platform_id)
    account = InvestmentAccount(user_id=current_user.id, **payload.model_dump())
    db.add(account)
    db.commit()
    db.refresh(account)
    account = db.scalars(
        select(InvestmentAccount)
        .options(selectinload(InvestmentAccount.platform))
        .where(InvestmentAccount.id == account.id)
    ).one()
    return investment_account_response(account)


@router.get("/cash-accounts", response_model=list[CashAccountRead])
def list_cash_accounts(db: DbSession, current_user: CurrentUser, portfolio_id: int | None = None):
    statement = (
        select(CashAccount)
        .options(selectinload(CashAccount.platform))
        .where(CashAccount.user_id == current_user.id)
    )
    if portfolio_id is not None:
        statement = statement.where(CashAccount.portfolio_id == portfolio_id)
    accounts = db.scalars(statement.order_by(CashAccount.id)).all()
    return [cash_account_response(account) for account in accounts]


@router.post("/cash-accounts", response_model=CashAccountRead, status_code=status.HTTP_201_CREATED)
def create_cash_account(payload: CashAccountCreate, db: DbSession, current_user: CurrentUser):
    ensure_portfolio(db, current_user.id, payload.portfolio_id)
    if payload.trading_platform_id is not None:
        platform_or_404(db, payload.trading_platform_id)
    data = payload.model_dump()
    data["balance_date"] = data["balance_date"] or date.today()
    data["currency"] = data["currency"].upper()
    account = CashAccount(user_id=current_user.id, **data)
    db.add(account)
    db.commit()
    db.refresh(account)
    account = db.scalars(
        select(CashAccount).options(selectinload(CashAccount.platform)).where(CashAccount.id == account.id)
    ).one()
    return cash_account_response(account)


@router.put("/cash-accounts/{account_id}", response_model=CashAccountRead)
def update_cash_account(account_id: int, payload: CashAccountUpdate, db: DbSession, current_user: CurrentUser):
    account = db.scalars(
        select(CashAccount)
        .options(selectinload(CashAccount.platform))
        .where(CashAccount.user_id == current_user.id, CashAccount.id == account_id)
        .limit(1)
    ).first()
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cash account not found")
    ensure_portfolio(db, current_user.id, payload.portfolio_id)
    if payload.trading_platform_id is not None:
        platform_or_404(db, payload.trading_platform_id)
    for key, value in payload.model_dump().items():
        if key == "balance_date" and value is None:
            value = date.today()
        if key == "currency":
            value = value.upper()
        setattr(account, key, value)
    db.commit()
    db.refresh(account)
    return cash_account_response(account)
