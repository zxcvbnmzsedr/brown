from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.models import Asset, AssetGroup, PortfolioBucket, PriceCache
from backend.schemas import (
    SnapshotBucket,
    SnapshotGroup,
    SnapshotItem,
    SnapshotResponse,
)
from backend.services.position import calculate_position
from backend.services.settings import get_rebalance_config


def latest_price_record_for_asset(db: Session, asset: Asset) -> PriceCache | None:
    return db.scalars(
        select(PriceCache)
        .where(PriceCache.asset_id == asset.id)
        .order_by(PriceCache.date.desc(), PriceCache.fetched_at.desc(), PriceCache.id.desc())
        .limit(1)
    ).first()


def latest_price_for_asset(db: Session, asset: Asset) -> float | None:
    if asset.type == "cash":
        return 1.0

    price = latest_price_record_for_asset(db, asset)
    return price.price if price else None


def _price_age_days(price_date: date | None) -> int | None:
    if price_date is None:
        return None
    return max((date.today() - price_date).days, 0)


def _price_state(asset: Asset, price: PriceCache | None, max_age_days: int) -> str:
    if asset.type == "cash":
        return "cash"
    if price is None:
        return "missing"
    age_days = _price_age_days(price.date)
    if age_days is not None and age_days > max_age_days:
        return "stale"
    return "fresh"


def _monitor_state_for_drift(
    actual_weight: float,
    target_weight: float,
    lower_bound: float,
    upper_bound: float,
) -> str:
    if actual_weight <= lower_bound or actual_weight >= upper_bound:
        return "rebalance"

    drift = abs(actual_weight - target_weight)
    if drift >= 0.10:
        return "warning"
    if drift >= 0.05:
        return "watch"
    return "ok"


def build_snapshot(db: Session) -> SnapshotResponse:
    config = get_rebalance_config(db)
    max_price_age_days = config.max_price_age_days
    buckets = db.scalars(
        select(PortfolioBucket)
        .options(selectinload(PortfolioBucket.groups))
        .order_by(PortfolioBucket.display_order, PortfolioBucket.id)
    ).all()
    assets = db.scalars(
        select(Asset)
        .options(selectinload(Asset.group).selectinload(AssetGroup.bucket), selectinload(Asset.transactions))
        .order_by(Asset.id)
    ).all()

    raw_items: list[dict] = []
    all_raw_items: list[dict] = []
    bucket_values: dict[int, float] = {bucket.id: 0.0 for bucket in buckets}
    group_values: dict[int, float] = {group.id: 0.0 for bucket in buckets for group in bucket.groups}
    total_value = 0.0
    total_holdings_value = 0.0
    pending_classification_count = 0
    pending_classification_value = 0.0
    stale_price_count = 0
    missing_price_count = 0

    for asset in assets:
        if not asset.is_active:
            continue

        group = asset.group
        bucket = group.bucket if group else None
        quantity, cost_basis = calculate_position(asset.transactions)
        price_record = latest_price_record_for_asset(db, asset) if asset.type != "cash" else None
        current_price = 1.0 if asset.type == "cash" else price_record.price if price_record else None
        price_state = _price_state(asset, price_record, max_price_age_days)
        current_value = quantity * current_price if current_price is not None else 0.0
        average_cost = cost_basis / quantity if quantity > 0 else None
        total_holdings_value += current_value

        row = {
            "asset": asset,
            "group": group,
            "bucket": bucket,
            "quantity": quantity,
            "cost_basis": cost_basis,
            "average_cost": average_cost,
            "current_price": current_price,
            "price_date": price_record.date if price_record else None,
            "price_fetched_at": price_record.fetched_at if price_record else None,
            "price_age_days": _price_age_days(price_record.date if price_record else None),
            "price_state": price_state,
            "current_value": current_value,
        }
        all_raw_items.append(row)

        if not asset.include_in_portfolio:
            if quantity > 0:
                pending_classification_count += 1
                pending_classification_value += current_value
            continue

        if price_state == "stale":
            stale_price_count += 1
        elif price_state == "missing":
            missing_price_count += 1

        total_value += current_value

        if bucket:
            bucket_values[bucket.id] = bucket_values.get(bucket.id, 0.0) + current_value
        if group:
            group_values[group.id] = group_values.get(group.id, 0.0) + current_value

        raw_items.append(row)

    snapshot_buckets = []
    for bucket in buckets:
        bucket_value = bucket_values.get(bucket.id, 0.0)
        bucket_actual_weight = bucket_value / total_value if total_value > 0 else 0
        if config.mode == "classic_35_15":
            lower_bound = config.lower_threshold
            upper_bound = config.upper_threshold
        else:
            span = max(
                config.upper_threshold - bucket.target_weight,
                bucket.target_weight - config.lower_threshold,
                0,
            )
            lower_bound = max(bucket.target_weight - span, 0)
            upper_bound = min(bucket.target_weight + span, 1)
        monitor_state = _monitor_state_for_drift(
            bucket_actual_weight,
            bucket.target_weight,
            lower_bound,
            upper_bound,
        )
        snapshot_groups = []
        for group in sorted(bucket.groups, key=lambda item: item.display_order):
            group_value = group_values.get(group.id, 0.0)
            group_actual_weight = group_value / total_value if total_value > 0 else 0
            snapshot_groups.append(
                SnapshotGroup(
                    group_id=group.id,
                    bucket_id=bucket.id,
                    name=group.name,
                    target_weight=group.target_weight,
                    current_value=group_value,
                    actual_weight=group_actual_weight,
                    drift=group_actual_weight - group.target_weight,
                )
            )
        snapshot_buckets.append(
            SnapshotBucket(
                bucket_id=bucket.id,
                name=bucket.name,
                target_weight=bucket.target_weight,
                current_value=bucket_value,
                actual_weight=bucket_actual_weight,
                drift=bucket_actual_weight - bucket.target_weight,
                lower_bound=lower_bound,
                upper_bound=upper_bound,
                distance_to_lower=bucket_actual_weight - lower_bound,
                distance_to_upper=upper_bound - bucket_actual_weight,
                monitor_state=monitor_state,
                groups=snapshot_groups,
            )
        )

    def snapshot_item(row: dict, denominator: float) -> SnapshotItem:
        actual_weight = row["current_value"] / denominator if denominator > 0 else 0
        target_weight = row["group"].target_weight if row["group"] else row["asset"].target_weight
        return SnapshotItem(
            asset_id=row["asset"].id,
            bucket_id=row["bucket"].id if row["bucket"] else None,
            bucket_name=row["bucket"].name if row["bucket"] else None,
            group_id=row["group"].id if row["group"] else None,
            group_name=row["group"].name if row["group"] else None,
            include_in_portfolio=row["asset"].include_in_portfolio,
            name=row["asset"].name,
            platform=row["asset"].platform,
            type=row["asset"].type,
            code=row["asset"].code,
            exchange=row["asset"].exchange,
            target_weight=target_weight,
            quantity=row["quantity"],
            cost_basis=row["cost_basis"],
            average_cost=row["average_cost"],
            current_price=row["current_price"],
            price_date=row["price_date"],
            price_fetched_at=row["price_fetched_at"],
            price_age_days=row["price_age_days"],
            price_state=row["price_state"],
            current_value=row["current_value"],
            actual_weight=actual_weight,
            drift=actual_weight - target_weight,
        )

    items = [
        snapshot_item(row, total_value)
        for row in raw_items
    ]
    all_items = [
        snapshot_item(row, total_holdings_value)
        for row in all_raw_items
    ]

    return SnapshotResponse(
        as_of=datetime.now(timezone.utc),
        total_value=total_value,
        total_holdings_value=total_holdings_value,
        target_weight_total=sum(bucket.target_weight for bucket in buckets),
        price_state="incomplete" if missing_price_count or stale_price_count else "ok",
        stale_price_count=stale_price_count,
        missing_price_count=missing_price_count,
        pending_classification_count=pending_classification_count,
        pending_classification_value=pending_classification_value,
        buckets=snapshot_buckets,
        items=items,
        all_items=all_items,
    )
