from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.db import get_db
from backend.models import AssetGroup, PortfolioBucket
from backend.schemas import BucketRead, SnapshotResponse
from backend.services.snapshot import build_snapshot
from backend.routers.buckets import bucket_response

router = APIRouter(tags=["portfolio"])

DbSession = Annotated[Session, Depends(get_db)]


@router.get("/portfolio/structure", response_model=list[BucketRead])
def portfolio_structure(db: DbSession):
    buckets = db.scalars(
        select(PortfolioBucket)
        .options(selectinload(PortfolioBucket.groups).selectinload(AssetGroup.bucket))
        .order_by(PortfolioBucket.display_order, PortfolioBucket.id)
    ).all()
    return [bucket_response(bucket) for bucket in buckets]


@router.get("/portfolio/snapshot", response_model=SnapshotResponse)
def portfolio_snapshot(db: DbSession):
    return build_snapshot(db)
