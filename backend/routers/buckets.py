from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.db import get_db
from backend.models import AssetGroup, PortfolioBucket
from backend.schemas import BucketCreate, BucketRead, BucketUpdate, GroupRead

router = APIRouter(prefix="/buckets", tags=["buckets"])

DbSession = Annotated[Session, Depends(get_db)]


def bucket_response(bucket: PortfolioBucket) -> BucketRead:
    def _group_response(group: AssetGroup) -> GroupRead:
        return GroupRead.model_validate(group).model_copy(
            update={"bucket_name": group.bucket.name if group.bucket else None}
        )

    return BucketRead(
        id=bucket.id,
        name=bucket.name,
        target_weight=bucket.target_weight,
        display_order=bucket.display_order,
        groups=[_group_response(group) for group in sorted(bucket.groups, key=lambda item: item.display_order)],
    )


def get_bucket_or_404(db: Session, bucket_id: int) -> PortfolioBucket:
    bucket = db.get(PortfolioBucket, bucket_id)
    if bucket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bucket not found")
    return bucket


@router.post("", response_model=BucketRead, status_code=status.HTTP_201_CREATED)
def create_bucket(payload: BucketCreate, db: DbSession):
    bucket = PortfolioBucket(**payload.model_dump())
    db.add(bucket)
    db.commit()
    db.refresh(bucket)
    return bucket_response(bucket)


@router.put("/{bucket_id}", response_model=BucketRead)
def update_bucket(bucket_id: int, payload: BucketUpdate, db: DbSession):
    bucket = get_bucket_or_404(db, bucket_id)
    for key, value in payload.model_dump().items():
        setattr(bucket, key, value)
    db.commit()
    db.refresh(bucket)
    return bucket_response(bucket)


@router.delete("/{bucket_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bucket(bucket_id: int, db: DbSession):
    bucket = get_bucket_or_404(db, bucket_id)
    if bucket.groups:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bucket still has groups")
    db.delete(bucket)
    db.commit()
