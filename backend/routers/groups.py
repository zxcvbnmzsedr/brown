from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.db import get_db
from backend.models import AssetGroup, PortfolioBucket
from backend.schemas import GroupCreate, GroupRead, GroupUpdate
from backend.routers.buckets import get_bucket_or_404

router = APIRouter(prefix="/groups", tags=["groups"])

DbSession = Annotated[Session, Depends(get_db)]


def group_response(group: AssetGroup) -> GroupRead:
    return GroupRead.model_validate(group).model_copy(
        update={"bucket_name": group.bucket.name if group.bucket else None}
    )


def get_group_or_404(db: Session, group_id: int) -> AssetGroup:
    group = db.get(AssetGroup, group_id)
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset group not found")
    return group


@router.post("", response_model=GroupRead, status_code=status.HTTP_201_CREATED)
def create_group(payload: GroupCreate, db: DbSession):
    get_bucket_or_404(db, payload.bucket_id)
    group = AssetGroup(**payload.model_dump())
    db.add(group)
    db.commit()
    db.refresh(group)
    group.bucket = get_bucket_or_404(db, group.bucket_id)
    return group_response(group)


@router.put("/{group_id}", response_model=GroupRead)
def update_group(group_id: int, payload: GroupUpdate, db: DbSession):
    get_bucket_or_404(db, payload.bucket_id)
    group = get_group_or_404(db, group_id)
    for key, value in payload.model_dump().items():
        setattr(group, key, value)
    db.commit()
    db.refresh(group)
    group.bucket = get_bucket_or_404(db, group.bucket_id)
    return group_response(group)


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(group_id: int, db: DbSession):
    group = get_group_or_404(db, group_id)
    if group.assets:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Asset group still has assets")
    db.delete(group)
    db.commit()
