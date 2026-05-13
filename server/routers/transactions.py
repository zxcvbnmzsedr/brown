from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from server.auth import CurrentUser
from server.db import get_db
from server.models import CashAccount, Instrument, InvestmentAccount, Portfolio, Transaction
from server.schemas import TransactionCreate, TransactionRead, TransactionUpdate
from server.services.portfolio import apply_cash_effect, ensure_user_asset, revert_cash_effect, transaction_amount

router = APIRouter(prefix="/transactions", tags=["transactions"])

DbSession = Annotated[Session, Depends(get_db)]


def validate_transaction_payload(db: Session, user_id: int, payload: TransactionCreate | TransactionUpdate) -> None:
    portfolio = db.scalars(select(Portfolio.id).where(Portfolio.user_id == user_id, Portfolio.id == payload.portfolio_id).limit(1)).first()
    if portfolio is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")
    instrument = db.get(Instrument, payload.instrument_id)
    if instrument is None or not instrument.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instrument not found")
    if payload.account_id is not None:
        account = db.scalars(
            select(InvestmentAccount)
            .where(
                InvestmentAccount.user_id == user_id,
                InvestmentAccount.portfolio_id == payload.portfolio_id,
                InvestmentAccount.id == payload.account_id,
            )
            .limit(1)
        ).first()
        if account is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investment account not found")
    if payload.cash_account_id is not None:
        cash_account = db.scalars(
            select(CashAccount)
            .where(
                CashAccount.user_id == user_id,
                CashAccount.portfolio_id == payload.portfolio_id,
                CashAccount.id == payload.cash_account_id,
            )
            .limit(1)
        ).first()
        if cash_account is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cash account not found")


def transaction_response(tx: Transaction) -> TransactionRead:
    return TransactionRead(
        id=tx.id,
        portfolio_id=tx.portfolio_id,
        instrument_id=tx.instrument_id,
        account_id=tx.account_id,
        cash_account_id=tx.cash_account_id,
        date=tx.date,
        type=tx.type,
        qty=tx.qty,
        price=tx.price,
        fee=tx.fee,
        note=tx.note,
        instrument_name=tx.instrument.name,
        instrument_code=tx.instrument.code,
        account_name=tx.account.name if tx.account else None,
        cash_account_name=tx.cash_account.name if tx.cash_account else None,
        amount=transaction_amount(tx.type, tx.qty, tx.price, tx.fee),
        created_at=tx.created_at,
    )


def get_transaction_or_404(db: Session, user_id: int, tx_id: int) -> Transaction:
    tx = db.scalars(
        select(Transaction)
        .options(
            selectinload(Transaction.instrument),
            selectinload(Transaction.account),
            selectinload(Transaction.cash_account),
        )
        .where(Transaction.user_id == user_id, Transaction.id == tx_id)
        .limit(1)
    ).first()
    if tx is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    return tx


@router.get("", response_model=list[TransactionRead])
def list_transactions(db: DbSession, current_user: CurrentUser, portfolio_id: int | None = None):
    statement = (
        select(Transaction)
        .options(
            selectinload(Transaction.instrument),
            selectinload(Transaction.account),
            selectinload(Transaction.cash_account),
        )
        .where(Transaction.user_id == current_user.id)
    )
    if portfolio_id is not None:
        statement = statement.where(Transaction.portfolio_id == portfolio_id)
    transactions = db.scalars(statement.order_by(Transaction.date.desc(), Transaction.id.desc())).all()
    return [transaction_response(tx) for tx in transactions]


@router.post("", response_model=TransactionRead, status_code=status.HTTP_201_CREATED)
def create_transaction(payload: TransactionCreate, db: DbSession, current_user: CurrentUser):
    validate_transaction_payload(db, current_user.id, payload)
    tx = Transaction(user_id=current_user.id, **payload.model_dump())
    cash_account = db.get(CashAccount, payload.cash_account_id) if payload.cash_account_id is not None else None
    apply_cash_effect(cash_account, tx.type, tx.qty, tx.price, tx.fee, tx.date)
    db.add(tx)
    db.flush()
    ensure_user_asset(db, current_user.id, tx.portfolio_id, tx.instrument_id, tx.account_id)
    db.commit()
    return transaction_response(get_transaction_or_404(db, current_user.id, tx.id))


@router.put("/{tx_id}", response_model=TransactionRead)
def update_transaction(tx_id: int, payload: TransactionUpdate, db: DbSession, current_user: CurrentUser):
    validate_transaction_payload(db, current_user.id, payload)
    tx = get_transaction_or_404(db, current_user.id, tx_id)
    old_cash = tx.cash_account
    revert_cash_effect(old_cash, tx.type, tx.qty, tx.price, tx.fee)
    for key, value in payload.model_dump().items():
        setattr(tx, key, value)
    new_cash = db.get(CashAccount, tx.cash_account_id) if tx.cash_account_id is not None else None
    apply_cash_effect(new_cash, tx.type, tx.qty, tx.price, tx.fee, tx.date)
    ensure_user_asset(db, current_user.id, tx.portfolio_id, tx.instrument_id, tx.account_id)
    db.commit()
    return transaction_response(get_transaction_or_404(db, current_user.id, tx.id))


@router.delete("/{tx_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(tx_id: int, db: DbSession, current_user: CurrentUser):
    tx = get_transaction_or_404(db, current_user.id, tx_id)
    revert_cash_effect(tx.cash_account, tx.type, tx.qty, tx.price, tx.fee)
    db.delete(tx)
    db.commit()
    return None
