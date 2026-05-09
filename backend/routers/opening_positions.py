from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.db import get_db
from backend.models import OpeningPosition, PriceCache
from backend.routers.assets import get_asset_or_404
from backend.schemas import OpeningPositionCreate, OpeningPositionRead, OpeningPositionUpdate

router = APIRouter(tags=["opening_positions"])

DbSession = Annotated[Session, Depends(get_db)]


def opening_position_response(opening_position: OpeningPosition) -> OpeningPositionRead:
    asset = opening_position.asset
    return OpeningPositionRead(
        id=opening_position.id,
        asset_id=opening_position.asset_id,
        date=opening_position.date,
        qty=opening_position.qty,
        cost_price=opening_position.cost_price,
        current_price=opening_position.current_price,
        note=opening_position.note,
        created_at=opening_position.created_at,
        asset_name=asset.name,
        asset_code=asset.code,
        asset_exchange=asset.exchange,
        include_in_portfolio=asset.include_in_portfolio,
    )


def sync_opening_price(db: Session, opening_position: OpeningPosition) -> None:
    asset = opening_position.asset
    price_value = 1.0 if asset.type == "cash" else opening_position.current_price
    existing = db.scalars(
        select(PriceCache)
        .where(PriceCache.asset_id == asset.id, PriceCache.date == opening_position.date)
        .order_by(PriceCache.id)
        .limit(1)
    ).first()

    if existing:
        existing.price = price_value
        return

    db.add(PriceCache(asset_id=asset.id, date=opening_position.date, price=price_value))


@router.get("/opening-positions", response_model=list[OpeningPositionRead])
def list_opening_positions(db: DbSession):
    opening_positions = db.scalars(
        select(OpeningPosition)
        .options(selectinload(OpeningPosition.asset))
        .order_by(OpeningPosition.date.desc(), OpeningPosition.id.desc())
    ).all()
    return [opening_position_response(opening_position) for opening_position in opening_positions]


@router.post("/opening-positions", response_model=OpeningPositionRead, status_code=status.HTTP_201_CREATED)
def upsert_opening_position(payload: OpeningPositionCreate, db: DbSession):
    asset = get_asset_or_404(db, payload.asset_id)
    opening_position = db.scalars(
        select(OpeningPosition).where(OpeningPosition.asset_id == asset.id).limit(1)
    ).first()

    if opening_position is None:
        opening_position = OpeningPosition(asset_id=asset.id)
        db.add(opening_position)

    opening_position.asset = asset
    opening_position.date = payload.date
    opening_position.qty = payload.qty
    opening_position.cost_price = payload.cost_price
    opening_position.current_price = payload.current_price
    opening_position.note = payload.note
    sync_opening_price(db, opening_position)

    db.commit()
    db.refresh(opening_position)
    db.refresh(opening_position, attribute_names=["asset"])
    return opening_position_response(opening_position)


@router.put("/opening-positions/{opening_position_id}", response_model=OpeningPositionRead)
def update_opening_position(opening_position_id: int, payload: OpeningPositionUpdate, db: DbSession):
    opening_position = db.get(OpeningPosition, opening_position_id)
    if opening_position is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opening position not found")

    update_data = payload.model_dump(exclude_unset=True)
    if "asset_id" in update_data:
        asset = get_asset_or_404(db, update_data["asset_id"])
        duplicate = db.scalars(
            select(OpeningPosition)
            .where(OpeningPosition.asset_id == asset.id, OpeningPosition.id != opening_position.id)
            .limit(1)
        ).first()
        if duplicate:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该标的已存在期初持仓")
        opening_position.asset = asset

    for key, value in update_data.items():
        setattr(opening_position, key, value)

    db.flush()
    db.refresh(opening_position, attribute_names=["asset"])
    sync_opening_price(db, opening_position)

    db.commit()
    db.refresh(opening_position)
    db.refresh(opening_position, attribute_names=["asset"])
    return opening_position_response(opening_position)


@router.delete("/opening-positions/{opening_position_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_opening_position(opening_position_id: int, db: DbSession):
    opening_position = db.get(OpeningPosition, opening_position_id)
    if opening_position is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opening position not found")
    db.delete(opening_position)
    db.commit()
