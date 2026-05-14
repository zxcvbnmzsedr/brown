from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from server.auth import CurrentUser
from server.db import get_db
from server.models import Instrument, InstrumentPrice, TradingPlatform
from server.schemas import InstrumentRead, TradingPlatformRead

router = APIRouter(tags=["catalog"])

DbSession = Annotated[Session, Depends(get_db)]


@router.get("/instruments", response_model=list[InstrumentRead])
def list_public_instruments(
    db: DbSession,
    _current_user: CurrentUser,
    q: str | None = None,
    instrument_type: str | None = None,
    limit: int = 20,
):
    statement = select(Instrument).where(Instrument.is_active == True)
    if instrument_type:
        statement = statement.where(Instrument.type == instrument_type)
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        statement = statement.where(or_(Instrument.name.ilike(pattern), Instrument.code.ilike(pattern)))
    safe_limit = min(max(limit, 1), 50)
    instruments = db.scalars(statement.order_by(Instrument.id).limit(safe_limit)).all()

    instrument_ids = [instrument.id for instrument in instruments]
    latest_prices: dict[int, InstrumentPrice] = {}
    if instrument_ids:
        latest_price_dates = (
            select(InstrumentPrice.instrument_id, func.max(InstrumentPrice.date).label("date"))
            .where(InstrumentPrice.instrument_id.in_(instrument_ids))
            .group_by(InstrumentPrice.instrument_id)
            .subquery()
        )
        price_rows = db.execute(
            select(InstrumentPrice)
            .join(
                latest_price_dates,
                (InstrumentPrice.instrument_id == latest_price_dates.c.instrument_id)
                & (InstrumentPrice.date == latest_price_dates.c.date),
            )
            .order_by(InstrumentPrice.instrument_id, InstrumentPrice.id.desc())
        ).scalars().all()
        for price in price_rows:
            latest_prices.setdefault(price.instrument_id, price)

    return [
        InstrumentRead.model_validate(instrument).model_copy(
            update={
                "latest_price": latest_prices[instrument.id].price if instrument.id in latest_prices else None,
                "price_date": latest_prices[instrument.id].date if instrument.id in latest_prices else None,
            }
        )
        for instrument in instruments
    ]


@router.get("/trading-platforms", response_model=list[TradingPlatformRead])
def list_public_trading_platforms(db: DbSession, _current_user: CurrentUser, usage: str | None = None):
    statement = select(TradingPlatform).where(TradingPlatform.is_active == True)
    if usage == "investment":
        statement = statement.where(TradingPlatform.type.in_(["broker", "fund_platform", "crypto_exchange", "other"]))
    elif usage == "cash":
        statement = statement.where(TradingPlatform.type.in_(["bank", "payment", "broker", "other"]))
    return db.scalars(statement.order_by(TradingPlatform.display_order, TradingPlatform.id)).all()
