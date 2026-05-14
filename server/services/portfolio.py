from __future__ import annotations

from collections import defaultdict
from calendar import monthrange
from datetime import date, timedelta

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
    ProfitCalendar,
    ProfitCalendarDay,
    ProfitCalendarSummary,
    PortfolioSnapshot,
    PortfolioTrend,
    SnapshotBucket,
    SnapshotHolding,
    TrendPoint,
    TrendSummary,
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


def build_trend(db: Session, user_id: int, portfolio_id: int, days: int = 90) -> PortfolioTrend:
    safe_days = max(7, min(days, 365))
    end_date = date.today()
    start_date = end_date - timedelta(days=safe_days - 1)
    points = build_trend_points(db, user_id, portfolio_id, start_date, end_date)

    start_value = points[0].total_value if points else 0.0
    end_value = points[-1].total_value if points else 0.0
    change_value = end_value - start_value
    return PortfolioTrend(
        portfolio_id=portfolio_id,
        start_date=start_date,
        end_date=end_date,
        points=points,
        summary=TrendSummary(
            start_value=start_value,
            end_value=end_value,
            change_value=change_value,
            change_rate=change_value / start_value if start_value else 0.0,
        ),
    )


def build_trend_points(db: Session, user_id: int, portfolio_id: int, start_date: date, end_date: date) -> list[TrendPoint]:
    if end_date < start_date:
        return []

    day_count = (end_date - start_date).days + 1
    dates = [start_date + timedelta(days=index) for index in range(day_count)]

    portfolio_exists = db.scalars(
        select(Portfolio.id).where(Portfolio.user_id == user_id, Portfolio.id == portfolio_id).limit(1)
    ).first()
    if portfolio_exists is None:
        raise ValueError("Portfolio not found")

    transactions = db.scalars(
        select(Transaction)
        .where(Transaction.user_id == user_id, Transaction.portfolio_id == portfolio_id)
        .order_by(Transaction.date, Transaction.id)
    ).all()
    cash_accounts = db.scalars(
        select(CashAccount)
        .where(
            CashAccount.user_id == user_id,
            CashAccount.portfolio_id == portfolio_id,
            CashAccount.is_active == True,
            CashAccount.include_in_rebalance == True,
        )
        .order_by(CashAccount.id)
    ).all()

    instrument_ids = sorted({tx.instrument_id for tx in transactions})
    price_rows = []
    if instrument_ids:
        price_rows = db.scalars(
            select(InstrumentPrice)
            .where(InstrumentPrice.instrument_id.in_(instrument_ids), InstrumentPrice.date <= end_date)
            .order_by(InstrumentPrice.instrument_id, InstrumentPrice.date, InstrumentPrice.id)
        ).all()

    price_dates_by_instrument: dict[int, list[tuple[date, float]]] = defaultdict(list)
    for price in price_rows:
        records = price_dates_by_instrument[price.instrument_id]
        if records and records[-1][0] == price.date:
            records[-1] = (price.date, price.price)
        else:
            records.append((price.date, price.price))

    prices_by_day: dict[date, dict[int, float]] = {item: {} for item in dates}
    for instrument_id, records in price_dates_by_instrument.items():
        cursor = 0
        latest_price: float | None = None
        for current_date in dates:
            while cursor < len(records) and records[cursor][0] <= current_date:
                latest_price = records[cursor][1]
                cursor += 1
            if latest_price is not None:
                prices_by_day[current_date][instrument_id] = latest_price

    txs_by_date: dict[date, list[Transaction]] = defaultdict(list)
    quantities: dict[int, float] = defaultdict(float)
    for tx in transactions:
        if tx.date < start_date:
            quantities[tx.instrument_id] += tx.qty if tx.type == "buy" else -tx.qty
        elif tx.date <= end_date:
            txs_by_date[tx.date].append(tx)

    current_cash_by_account = {
        account.id: account.balance
        for account in cash_accounts
    }
    cash_account_ids = set(current_cash_by_account)
    cash_deltas_by_date: dict[date, float] = defaultdict(float)
    for tx in transactions:
        if tx.cash_account_id not in cash_account_ids or tx.date > end_date:
            continue
        cash_deltas_by_date[tx.date] += signed_cash_delta(tx.type, tx.qty, tx.price, tx.fee)

    current_cash_value = sum(current_cash_by_account.values())
    cash_value_by_date: dict[date, float] = {}
    running_cash = current_cash_value
    for current_date in reversed(dates):
        cash_value_by_date[current_date] = running_cash
        running_cash -= cash_deltas_by_date.get(current_date, 0.0)

    points: list[TrendPoint] = []
    for current_date in dates:
        for tx in txs_by_date.get(current_date, []):
            quantities[tx.instrument_id] += tx.qty if tx.type == "buy" else -tx.qty

        holdings_value = 0.0
        day_prices = prices_by_day[current_date]
        for instrument_id, quantity in quantities.items():
            if abs(quantity) < 1e-9:
                continue
            price = day_prices.get(instrument_id)
            if price is not None:
                holdings_value += quantity * price

        cash_value = cash_value_by_date[current_date]
        points.append(
            TrendPoint(
                date=current_date,
                total_value=holdings_value + cash_value,
                holdings_value=holdings_value,
                cash_value=cash_value,
            )
        )

    return points


def build_profit_calendar(db: Session, user_id: int, portfolio_id: int, year: int, month: int) -> ProfitCalendar:
    safe_month = max(1, min(month, 12))
    safe_year = max(1970, min(year, 9999))
    start_date = date(safe_year, safe_month, 1)
    end_date = date(safe_year, safe_month, monthrange(safe_year, safe_month)[1])
    prior_date = start_date - timedelta(days=1)
    trend_points = build_trend_points(db, user_id, portfolio_id, prior_date, end_date)

    transactions = db.scalars(
        select(Transaction)
        .where(
            Transaction.user_id == user_id,
            Transaction.portfolio_id == portfolio_id,
            Transaction.date >= start_date,
            Transaction.date <= end_date,
        )
        .order_by(Transaction.date, Transaction.id)
    ).all()
    txs_by_date: dict[date, list[Transaction]] = defaultdict(list)
    for tx in transactions:
        txs_by_date[tx.date].append(tx)

    previous_total = trend_points[0].total_value if trend_points else 0.0
    days: list[ProfitCalendarDay] = []
    for point in trend_points[1:]:
        day_transactions = txs_by_date.get(point.date, [])
        change_value = point.total_value - previous_total
        buy_amount = sum(transaction_amount(tx.type, tx.qty, tx.price, tx.fee) for tx in day_transactions if tx.type == "buy")
        sell_amount = sum(transaction_amount(tx.type, tx.qty, tx.price, tx.fee) for tx in day_transactions if tx.type == "sell")
        fee = sum(tx.fee for tx in day_transactions)
        days.append(
            ProfitCalendarDay(
                date=point.date,
                total_value=point.total_value,
                holdings_value=point.holdings_value,
                cash_value=point.cash_value,
                change_value=change_value,
                change_rate=change_value / previous_total if previous_total else 0.0,
                buy_amount=buy_amount,
                sell_amount=sell_amount,
                fee=fee,
                transaction_count=len(day_transactions),
            )
        )
        previous_total = point.total_value

    first_value = trend_points[0].total_value if trend_points else 0.0
    last_value = trend_points[-1].total_value if trend_points else 0.0
    month_change = last_value - first_value
    return ProfitCalendar(
        portfolio_id=portfolio_id,
        start_date=start_date,
        end_date=end_date,
        year=safe_year,
        month=safe_month,
        days=days,
        summary=ProfitCalendarSummary(
            month_change=month_change,
            month_change_rate=month_change / first_value if first_value else 0.0,
            positive_days=sum(1 for day in days if day.change_value > 0),
            negative_days=sum(1 for day in days if day.change_value < 0),
            flat_days=sum(1 for day in days if day.change_value == 0),
            buy_amount=sum(day.buy_amount for day in days),
            sell_amount=sum(day.sell_amount for day in days),
            fee=sum(day.fee for day in days),
        ),
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
