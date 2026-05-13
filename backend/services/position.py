from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import OpeningPosition, Transaction
from backend.utils.decimal_math import QTY_EPSILON, ZERO, quantize_money, quantize_qty, to_decimal


def calculate_position(
    transactions: list[Transaction],
    opening_position: OpeningPosition | None = None,
) -> tuple[float, float]:
    quantity = to_decimal(opening_position.qty) if opening_position else ZERO
    cost_basis = (
        to_decimal(opening_position.qty) * to_decimal(opening_position.cost_price)
        if opening_position
        else ZERO
    )

    for transaction in sorted(transactions, key=lambda item: (item.date, item.id)):
        qty = to_decimal(transaction.qty)
        price = to_decimal(transaction.price)
        fee = to_decimal(transaction.fee)

        if transaction.type == "buy":
            quantity += qty
            cost_basis += qty * price + fee
            continue

        if quantity <= ZERO:
            quantity -= qty
            cost_basis = ZERO
            continue

        average_cost = cost_basis / quantity
        quantity -= qty
        cost_basis -= average_cost * qty
        if quantity <= QTY_EPSILON:
            quantity = ZERO
            cost_basis = ZERO

    return float(quantize_qty(max(quantity, ZERO))), float(quantize_money(max(cost_basis, ZERO)))


def get_current_quantity(db: Session, user_id: int, asset_id: int) -> float:
    transactions = db.scalars(
        select(Transaction)
        .where(Transaction.user_id == user_id, Transaction.asset_id == asset_id)
        .order_by(Transaction.date, Transaction.id)
    ).all()
    opening_position = db.scalars(
        select(OpeningPosition)
        .where(OpeningPosition.user_id == user_id, OpeningPosition.asset_id == asset_id)
        .limit(1)
    ).first()
    quantity, _cost = calculate_position(list(transactions), opening_position)
    return quantity
