from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from server.auth import CurrentUser
from server.db import get_db
from server.models import Portfolio, PortfolioBucket
from server.schemas import PortfolioGroupUpdate, PortfolioRead, PortfolioSnapshot, PortfolioTrend, ProfitCalendar
from server.services.portfolio import build_profit_calendar, build_snapshot, build_trend

router = APIRouter(prefix="/portfolios", tags=["portfolios"])

DbSession = Annotated[Session, Depends(get_db)]


def get_portfolio_or_404(db: Session, user_id: int, portfolio_id: int) -> Portfolio:
    portfolio = db.scalars(
        select(Portfolio)
        .options(selectinload(Portfolio.buckets).selectinload(PortfolioBucket.groups))
        .where(Portfolio.user_id == user_id, Portfolio.id == portfolio_id)
        .limit(1)
    ).first()
    if portfolio is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")
    return portfolio


@router.get("", response_model=list[PortfolioRead])
def list_portfolios(db: DbSession, current_user: CurrentUser):
    portfolios = db.scalars(
        select(Portfolio)
        .options(selectinload(Portfolio.buckets).selectinload(PortfolioBucket.groups))
        .where(Portfolio.user_id == current_user.id)
        .order_by(Portfolio.is_default.desc(), Portfolio.id)
    ).all()
    return portfolios


@router.get("/{portfolio_id}", response_model=PortfolioRead)
def get_portfolio(portfolio_id: int, db: DbSession, current_user: CurrentUser):
    return get_portfolio_or_404(db, current_user.id, portfolio_id)


@router.put("/groups/{group_id}", response_model=PortfolioRead)
def update_group(group_id: int, payload: PortfolioGroupUpdate, db: DbSession, current_user: CurrentUser):
    from server.models import PortfolioGroup

    group = db.scalars(
        select(PortfolioGroup).where(PortfolioGroup.user_id == current_user.id, PortfolioGroup.id == group_id).limit(1)
    ).first()
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio group not found")
    group.name = payload.name
    group.target_weight = payload.target_weight
    group.display_order = payload.display_order
    db.commit()
    return get_portfolio_or_404(db, current_user.id, group.portfolio_id)


@router.get("/{portfolio_id}/snapshot", response_model=PortfolioSnapshot)
def snapshot(portfolio_id: int, db: DbSession, current_user: CurrentUser):
    get_portfolio_or_404(db, current_user.id, portfolio_id)
    return build_snapshot(db, current_user.id, portfolio_id)


@router.get("/{portfolio_id}/trend", response_model=PortfolioTrend)
def trend(portfolio_id: int, db: DbSession, current_user: CurrentUser, days: int = 90):
    get_portfolio_or_404(db, current_user.id, portfolio_id)
    return build_trend(db, current_user.id, portfolio_id, days)


@router.get("/{portfolio_id}/profit-calendar", response_model=ProfitCalendar)
def profit_calendar(portfolio_id: int, db: DbSession, current_user: CurrentUser, year: int, month: int):
    get_portfolio_or_404(db, current_user.id, portfolio_id)
    return build_profit_calendar(db, current_user.id, portfolio_id, year, month)
