from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.db import get_db
from backend.models import Transaction
from backend.schemas import TransactionCreate, TransactionRead, TransactionUpdate
from backend.services.position import get_current_quantity
from backend.routers.assets import create_unclassified_asset, get_asset_or_404

router = APIRouter(tags=["transactions"])

DbSession = Annotated[Session, Depends(get_db)]


def transaction_response(transaction: Transaction) -> TransactionRead:
    return TransactionRead(
        id=transaction.id,
        date=transaction.date,
        asset_id=transaction.asset_id,
        type=transaction.type,
        qty=transaction.qty,
        price=transaction.price,
        fee=transaction.fee,
        note=transaction.note,
        created_at=transaction.created_at,
        asset_name=transaction.asset.name,
    )


@router.get("/transactions", response_model=list[TransactionRead])
def list_transactions(
    db: DbSession,
    asset_id: int | None = None,
    type: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
):
    statement = select(Transaction).options(selectinload(Transaction.asset))
    if asset_id is not None:
        statement = statement.where(Transaction.asset_id == asset_id)
    if type is not None:
        statement = statement.where(Transaction.type == type)
    if date_from is not None:
        statement = statement.where(Transaction.date >= date_from)
    if date_to is not None:
        statement = statement.where(Transaction.date <= date_to)

    transactions = db.scalars(statement.order_by(Transaction.date.desc(), Transaction.id.desc())).all()
    return [transaction_response(transaction) for transaction in transactions]


@router.post("/transactions", response_model=TransactionRead, status_code=status.HTTP_201_CREATED)
def create_transaction(payload: TransactionCreate, db: DbSession):
    if payload.asset_id is None and payload.asset is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请选择或搜索确认一个标的")

    asset = (
        get_asset_or_404(db, payload.asset_id)
        if payload.asset_id is not None
        else create_unclassified_asset(db, payload.asset, fallback_price=payload.price)
    )
    if payload.type == "sell":
        current_quantity = get_current_quantity(db, asset.id)
        if payload.qty > current_quantity + 0.0000001:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Sell quantity exceeds current holding ({current_quantity:.4f})",
            )

    transaction = Transaction(
        date=payload.date,
        asset_id=asset.id,
        type=payload.type,
        qty=payload.qty,
        price=payload.price,
        fee=payload.fee,
        note=payload.note,
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    transaction.asset = asset
    return transaction_response(transaction)


@router.put("/transactions/{transaction_id}", response_model=TransactionRead)
def update_transaction(transaction_id: int, payload: TransactionUpdate, db: DbSession):
    transaction = db.get(Transaction, transaction_id)
    if transaction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")

    update_data = payload.model_dump(exclude_unset=True)

    if "asset_id" in update_data:
        get_asset_or_404(db, update_data["asset_id"])

    if "qty" in update_data and update_data.get("type", transaction.type) == "sell":
        asset_id = update_data.get("asset_id", transaction.asset_id)
        current_quantity = get_current_quantity(db, asset_id)
        new_qty = update_data["qty"]
        if new_qty > current_quantity + 0.0000001:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Sell quantity exceeds current holding ({current_quantity:.4f})",
            )

    for key, value in update_data.items():
        setattr(transaction, key, value)

    db.commit()
    db.refresh(transaction)
    db.refresh(transaction, attribute_names=["asset"])
    return transaction_response(transaction)


@router.delete("/transactions/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(transaction_id: int, db: DbSession):
    transaction = db.get(Transaction, transaction_id)
    if transaction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    db.delete(transaction)
    db.commit()
