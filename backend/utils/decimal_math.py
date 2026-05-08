from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP, ROUND_DOWN

ZERO = Decimal("0")
MONEY_EPSILON = Decimal("0.01")
QTY_EPSILON = Decimal("0.0001")


def to_decimal(value: float | int | str | Decimal) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def quantize_money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def quantize_qty(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"), rounding=ROUND_DOWN)


def quantize_shares(value: Decimal, lot_size: int = 1) -> int:
    if lot_size <= 1:
        return int(value)
    return int(value / lot_size) * lot_size


def to_float(value: Decimal) -> float:
    return float(value)
