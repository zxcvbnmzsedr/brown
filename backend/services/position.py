from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import Transaction
from backend.utils.decimal_math import QTY_EPSILON, ZERO, quantize_money, quantize_qty, to_decimal


def calculate_position(transactions: list[Transaction]) -> tuple[float, float]:
    quantity = ZERO
    cost_basis = ZERO

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


def get_current_quantity(db: Session, asset_id: int) -> float:
    transactions = db.scalars(
        select(Transaction).where(Transaction.asset_id == asset_id).order_by(Transaction.date, Transaction.id)
    ).all()
    quantity, _cost = calculate_position(list(transactions))
    return quantity
