from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db import get_db
from backend.models import Asset
from backend.services.price_fetcher import PriceFetcher
from backend.services.settings import get_rebalance_config

router = APIRouter(tags=["prices"])

DbSession = Annotated[Session, Depends(get_db)]


class FetchResult(BaseModel):
    updated: int
    errors: list[str]


class AssetPriceStatus(BaseModel):
    asset_id: int
    asset_name: str
    last_fetched_at: str | None
    latest_price: float | None
    price_age_days: int | None
    price_state: str


@router.post("/prices/fetch", response_model=FetchResult)
async def fetch_all_prices(db: DbSession):
    fetcher = PriceFetcher()
    try:
        prices = await fetcher.fetch_all_prices(db)
        count = fetcher.save_prices(db, prices)
        return FetchResult(updated=count, errors=[])
    except Exception as e:
        return FetchResult(updated=0, errors=[str(e)])
    finally:
        await fetcher.close()


@router.post("/prices/fetch/{asset_id}", response_model=FetchResult)
async def fetch_single_price(asset_id: int, db: DbSession):
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")

    fetcher = PriceFetcher()
    try:
        price = await fetcher.fetch_asset_price(asset)
        if price is None:
            return FetchResult(updated=0, errors=[f"Failed to fetch price for {asset.name}"])
        count = fetcher.save_prices(db, {asset_id: price})
        return FetchResult(updated=count, errors=[])
    except Exception as e:
        return FetchResult(updated=0, errors=[str(e)])
    finally:
        await fetcher.close()


@router.get("/prices/status", response_model=list[AssetPriceStatus])
def price_status(db: DbSession):
    from datetime import date

    from backend.services.snapshot import latest_price_record_for_asset

    config = get_rebalance_config(db)
    assets = db.scalars(select(Asset).where(Asset.is_active == True).order_by(Asset.id)).all()
    result = []
    for asset in assets:
        price_record = latest_price_record_for_asset(db, asset) if asset.type != "cash" else None
        latest_price = 1.0 if asset.type == "cash" else price_record.price if price_record else None
        age_days = None if price_record is None else max((date.today() - price_record.date).days, 0)
        if asset.type == "cash":
            price_state = "cash"
        elif price_record is None:
            price_state = "missing"
        elif age_days is not None and age_days > config.max_price_age_days:
            price_state = "stale"
        else:
            price_state = "fresh"
        result.append(
            AssetPriceStatus(
                asset_id=asset.id,
                asset_name=asset.name,
                last_fetched_at=asset.last_fetched_at.isoformat() if asset.last_fetched_at else None,
                latest_price=latest_price,
                price_age_days=age_days,
                price_state=price_state,
            )
        )
    return result
