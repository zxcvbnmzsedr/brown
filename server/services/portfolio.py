from __future__ import annotations

from collections import defaultdict
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from server.models import (
    CashAccount,
    Instrument,
    InstrumentPrice,
    Portfolio,
    PortfolioBucket,
    PortfolioGroup,
    Transaction,
    UserAsset,
)
from server.schemas import (
    CashAccountRead,
    PortfolioSnapshot,
    SnapshotBucket,
    SnapshotHolding,
    UserAssetRead,
)


def latest_price_record_for_instrument(db: Session, instrument_id: int) -> InstrumentPrice | None:
    return db.scalars(
        select(InstrumentPrice)
        .where(InstrumentPrice.instrument_id == instrument_id)
        .order_by(InstrumentPrice.date.desc(), InstrumentPrice.id.desc())
        .limit(1)
    ).first()


def latest_price_for_instrument(db: Session, instrument_id: int) -> float | None:
    record = latest_price_record_for_instrument(db, instrument_id)
    return record.price if record else None


def transaction_amount(tx_type: str, qty: float, price: float, fee: float) -> float:
    gross = qty * price
    return gross + fee if tx_type == "buy" else gross - fee


def signed_cash_delta(tx_type: str, qty: float, price: float, fee: float) -> float:
    amount = transaction_amount(tx_type, qty, price, fee)
    return -amount if tx_type == "buy" else amount


def apply_cash_effect(cash_account: CashAccount | None, tx_type: str, qty: float, price: float, fee: float, tx_date: date) -> None:
    if cash_account is None:
        return
    cash_account.balance += signed_cash_delta(tx_type, qty, price, fee)
    cash_account.balance_date = tx_date


def revert_cash_effect(cash_account: CashAccount | None, tx_type: str, qty: float, price: float, fee: float) -> None:
    if cash_account is None:
        return
    cash_account.balance -= signed_cash_delta(tx_type, qty, price, fee)


def position_totals(db: Session, user_id: int, portfolio_id: int) -> dict[int, tuple[float, float]]:
    rows = db.scalars(
        select(Transaction).where(Transaction.user_id == user_id, Transaction.portfolio_id == portfolio_id)
    ).all()
    totals: dict[int, list[float]] = defaultdict(lambda: [0.0, 0.0])
    for tx in rows:
        sign = 1 if tx.type == "buy" else -1
        totals[tx.instrument_id][0] += sign * tx.qty
        totals[tx.instrument_id][1] += sign * transaction_amount(tx.type, tx.qty, tx.price, tx.fee)
    return {instrument_id: (values[0], values[1]) for instrument_id, values in totals.items()}


def ensure_user_asset(db: Session, user_id: int, portfolio_id: int, instrument_id: int, account_id: int | None) -> UserAsset:
    existing = db.scalars(
        select(UserAsset)
        .where(
            UserAsset.user_id == user_id,
            UserAsset.portfolio_id == portfolio_id,
            UserAsset.instrument_id == instrument_id,
        )
        .limit(1)
    ).first()
    if existing is not None:
        if account_id is not None and existing.account_id is None:
            existing.account_id = account_id
        return existing

    asset = UserAsset(
        user_id=user_id,
        portfolio_id=portfolio_id,
        instrument_id=instrument_id,
        account_id=account_id,
        include_in_rebalance=True,
        is_active=True,
    )
    db.add(asset)
    db.flush()
    return asset


def user_asset_read(db: Session, asset: UserAsset, quantity: float | None = None, cost_basis: float | None = None) -> UserAssetRead:
    instrument = asset.instrument
    latest_price = latest_price_for_instrument(db, instrument.id)
    qty = quantity if quantity is not None else 0
    cost = cost_basis if cost_basis is not None else 0
    market_value = qty * latest_price if latest_price is not None else 0
    return UserAssetRead(
        id=asset.id,
        portfolio_id=asset.portfolio_id,
        instrument_id=asset.instrument_id,
        portfolio_group_id=asset.portfolio_group_id,
        account_id=asset.account_id,
        display_name=asset.display_name,
        target_weight=asset.target_weight,
        include_in_rebalance=asset.include_in_rebalance,
        is_active=asset.is_active,
        instrument_name=asset.display_name or instrument.name,
        instrument_type=instrument.type,
        instrument_code=instrument.code,
        instrument_exchange=instrument.exchange,
        group_name=asset.group.name if asset.group else None,
        bucket_name=asset.group.bucket.name if asset.group else None,
        account_name=asset.account.name if asset.account else None,
        quantity=qty,
        cost_basis=cost,
        market_value=market_value,
        latest_price=latest_price,
    )


def build_snapshot(db: Session, user_id: int, portfolio_id: int) -> PortfolioSnapshot:
    portfolio = db.scalars(
        select(Portfolio)
        .options(selectinload(Portfolio.buckets).selectinload(PortfolioBucket.groups))
        .where(Portfolio.user_id == user_id, Portfolio.id == portfolio_id)
        .limit(1)
    ).first()
    if portfolio is None:
        raise ValueError("Portfolio not found")

    totals = position_totals(db, user_id, portfolio_id)
    assets = db.scalars(
        select(UserAsset)
        .options(
            selectinload(UserAsset.instrument),
            selectinload(UserAsset.group).selectinload(PortfolioGroup.bucket),
            selectinload(UserAsset.account),
        )
        .where(UserAsset.user_id == user_id, UserAsset.portfolio_id == portfolio_id, UserAsset.is_active == True)
        .order_by(UserAsset.id)
    ).all()
    cash_accounts = db.scalars(
        select(CashAccount)
        .options(selectinload(CashAccount.platform))
        .where(CashAccount.user_id == user_id, CashAccount.portfolio_id == portfolio_id, CashAccount.is_active == True)
        .order_by(CashAccount.id)
    ).all()

    holdings: list[SnapshotHolding] = []
    bucket_values: dict[str, float] = defaultdict(float)
    holdings_value = 0.0
    for asset in assets:
        quantity, cost_basis = totals.get(asset.instrument_id, (0.0, 0.0))
        if abs(quantity) < 1e-9:
            continue
        latest_price = latest_price_for_instrument(db, asset.instrument_id)
        market_value = quantity * latest_price if latest_price is not None else 0.0
        holdings_value += market_value
        bucket_name = asset.group.bucket.name if asset.group else None
        if bucket_name:
            bucket_values[bucket_name] += market_value
        holdings.append(
            SnapshotHolding(
                user_asset_id=asset.id,
                instrument_id=asset.instrument_id,
                instrument_code=asset.instrument.code,
                instrument_exchange=asset.instrument.exchange,
                name=asset.display_name or asset.instrument.name,
                bucket_name=bucket_name,
                group_name=asset.group.name if asset.group else None,
                quantity=quantity,
                cost_basis=cost_basis,
                average_cost=cost_basis / quantity if quantity else 0,
                latest_price=latest_price,
                market_value=market_value,
            )
        )

    cash_value = sum(account.balance for account in cash_accounts if account.include_in_rebalance)
    bucket_values["现金"] += cash_value
    total_value = holdings_value + cash_value

    buckets: list[SnapshotBucket] = []
    for bucket in sorted(portfolio.buckets, key=lambda item: item.display_order):
        current_value = bucket_values.get(bucket.name, 0.0)
        buckets.append(
            SnapshotBucket(
                bucket_id=bucket.id,
                name=bucket.name,
                target_weight=bucket.target_weight,
                current_value=current_value,
                actual_weight=current_value / total_value if total_value else 0,
            )
        )

    return PortfolioSnapshot(
        portfolio_id=portfolio.id,
        total_value=total_value,
        holdings_value=holdings_value,
        cash_value=cash_value,
        holdings=holdings,
        cash_accounts=[
            CashAccountRead(
                id=account.id,
                portfolio_id=account.portfolio_id,
                trading_platform_id=account.trading_platform_id,
                name=account.name,
                currency=account.currency,
                balance=account.balance,
                balance_date=account.balance_date,
                include_in_rebalance=account.include_in_rebalance,
                is_active=account.is_active,
                platform_name=account.platform.name if account.platform else None,
            )
            for account in cash_accounts
        ],
        buckets=buckets,
    )


def latest_price_map(db: Session) -> dict[int, float]:
    rows = db.execute(
        select(InstrumentPrice.instrument_id, func.max(InstrumentPrice.date)).group_by(InstrumentPrice.instrument_id)
    ).all()
    prices: dict[int, float] = {}
    for instrument_id, price_date in rows:
        record = db.scalars(
            select(InstrumentPrice)
            .where(InstrumentPrice.instrument_id == instrument_id, InstrumentPrice.date == price_date)
            .order_by(InstrumentPrice.id.desc())
            .limit(1)
        ).first()
        if record:
            prices[instrument_id] = record.price
    return prices
