from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from server.auth import CurrentUser
from server.db import get_db
from server.models import Instrument, TradingPlatform
from server.routers.admin import instrument_response
from server.schemas import InstrumentRead, TradingPlatformRead

router = APIRouter(tags=["catalog"])

DbSession = Annotated[Session, Depends(get_db)]


@router.get("/instruments", response_model=list[InstrumentRead])
def list_public_instruments(
    db: DbSession,
    _current_user: CurrentUser,
    q: str | None = None,
    instrument_type: str | None = None,
):
    statement = select(Instrument).where(Instrument.is_active == True)
    if instrument_type:
        statement = statement.where(Instrument.type == instrument_type)
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        statement = statement.where(or_(Instrument.name.ilike(pattern), Instrument.code.ilike(pattern)))
    instruments = db.scalars(statement.order_by(Instrument.id)).all()
    return [instrument_response(db, instrument) for instrument in instruments]


@router.get("/trading-platforms", response_model=list[TradingPlatformRead])
def list_public_trading_platforms(db: DbSession, _current_user: CurrentUser, usage: str | None = None):
    statement = select(TradingPlatform).where(TradingPlatform.is_active == True)
    if usage == "investment":
        statement = statement.where(TradingPlatform.type.in_(["broker", "fund_platform", "crypto_exchange", "other"]))
    elif usage == "cash":
        statement = statement.where(TradingPlatform.type.in_(["bank", "payment", "broker", "other"]))
    return db.scalars(statement.order_by(TradingPlatform.display_order, TradingPlatform.id)).all()
