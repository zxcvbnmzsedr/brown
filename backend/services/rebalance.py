from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.schemas import AssetAction, BucketRebalanceDetail, GroupRebalanceDetail, RebalancePlanResponse, RebalanceResponse, RebalanceSuggestion
from backend.services.position import calculate_position
from backend.services.settings import get_rebalance_config
from backend.services.snapshot import build_snapshot, latest_price_for_asset


def compute_rebalance(db: Session, threshold: float = 0.15) -> RebalanceResponse:
    snapshot = build_snapshot(db)
    suggestions: list[RebalanceSuggestion] = []

    if snapshot.total_value <= 0:
        return RebalanceResponse(threshold=threshold, triggered=False, total_value=0, suggestions=[])

    for bucket in snapshot.buckets:
        if abs(bucket.drift) < threshold:
            continue

        target_value = snapshot.total_value * bucket.target_weight
        amount = abs(target_value - bucket.current_value)
        if amount <= 0.0000001:
            continue

        candidate_assets = [
            item.name
            for item in snapshot.items
            if item.bucket_id == bucket.bucket_id and item.current_price is not None
        ]
        suggestions.append(
            RebalanceSuggestion(
                scope="bucket",
                bucket_id=bucket.bucket_id,
                name=bucket.name,
                action="buy" if target_value > bucket.current_value else "sell",
                drift=bucket.drift,
                target_value=target_value,
                current_value=bucket.current_value,
                amount=amount,
                candidate_assets=candidate_assets,
            )
        )

    return RebalanceResponse(
        threshold=threshold,
        triggered=bool(suggestions),
        total_value=snapshot.total_value,
        suggestions=suggestions,
    )


def _determine_lot_size(asset_type: str, exchange: str | None) -> int:
    if asset_type == "stock" and exchange in ("SH", "SZ", "SSE"):
        return 100
    return 1


def _rule_bounds(target_weight: float, lower_threshold: float, upper_threshold: float, mode: str) -> tuple[float, float]:
    if mode == "classic_35_15":
        return lower_threshold, upper_threshold
    span = max(upper_threshold - target_weight, target_weight - lower_threshold, 0)
    return max(target_weight - span, 0), min(target_weight + span, 1)


def _bucket_monitor_state(weight: float, target_weight: float, lower: float, upper: float, watch: float, warning: float) -> str:
    if weight <= lower or weight >= upper:
        return "rebalance"

    drift = abs(weight - target_weight)
    if drift >= warning:
        return "warning"
    if drift >= watch:
        return "watch"
    return "ok"


def _rank_status(current: str, candidate: str) -> str:
    order = {"ok": 0, "watch": 1, "warning": 2, "rebalance": 3, "incomplete": 4}
    return candidate if order[candidate] > order[current] else current


def _status_label(status: str) -> str:
    return {
        "ok": "当前无需操作",
        "watch": "进入观察区",
        "warning": "接近再平衡区",
        "rebalance": "需要再平衡",
        "incomplete": "价格数据不完整",
    }[status]


def _status_message(status: str) -> str:
    return {
        "ok": "四大资产桶都在纪律区间内。",
        "watch": "有资产桶出现轻微偏离，暂不需要交易。",
        "warning": "有资产桶偏离较大，建议关注价格和现金安排。",
        "rebalance": "至少一个资产桶触发 35/15 纪律区间。",
        "incomplete": "存在缺失或过期价格，先补齐价格再生成交易清单。",
    }[status]


def compute_rebalance_plan(db: Session) -> RebalancePlanResponse:
    config = get_rebalance_config(db)
    snapshot = build_snapshot(db)
    total_value = snapshot.total_value

    if total_value <= 0:
        return RebalancePlanResponse(
            config=config,
            status="ok",
            status_label=_status_label("ok"),
            status_message="暂无持仓数据，录入交易后再开始监控。",
            triggered=False,
            total_value=0,
            as_of=datetime.now(timezone.utc),
            trigger_reasons=[],
            price_warnings=[],
            buckets=[],
            trade_list=[],
        )

    trigger_reasons: list[str] = []
    price_warnings: list[str] = []
    plan_status = "ok"

    for bucket in snapshot.buckets:
        weight = bucket.actual_weight
        lower, upper = _rule_bounds(
            bucket.target_weight,
            config.lower_threshold,
            config.upper_threshold,
            config.mode,
        )
        bucket_status = _bucket_monitor_state(
            weight,
            bucket.target_weight,
            lower,
            upper,
            config.watch_drift,
            config.warning_drift,
        )
        plan_status = _rank_status(plan_status, bucket_status)

        if bucket_status == "rebalance":
            if weight >= upper:
                trigger_reasons.append(f"{bucket.name}达到{weight:.1%}，超过{upper:.0%}上限")
            else:
                trigger_reasons.append(f"{bucket.name}降至{weight:.1%}，低于{lower:.0%}下限")

    for item in snapshot.items:
        if item.quantity <= 0:
            continue
        if item.price_state == "missing":
            price_warnings.append(f"{item.name}缺少价格")
        elif item.price_state == "stale":
            price_warnings.append(f"{item.name}价格已过期 {item.price_age_days} 天")

    if price_warnings:
        plan_status = "incomplete"

    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from backend.models import Asset, AssetGroup, PortfolioBucket

    all_assets = db.scalars(
        select(Asset)
        .options(
            selectinload(Asset.group).selectinload(AssetGroup.bucket),
            selectinload(Asset.opening_position),
            selectinload(Asset.transactions),
        )
        .where(Asset.is_active == True, Asset.include_in_portfolio == True)
        .order_by(Asset.id)
    ).all()

    asset_positions: dict[int, tuple[float, float]] = {}
    for asset in all_assets:
        qty, cost = calculate_position(asset.transactions, asset.opening_position)
        asset_positions[asset.id] = (qty, cost)

    bucket_details: list[BucketRebalanceDetail] = []
    all_actions: list[AssetAction] = []

    for bucket in snapshot.buckets:
        target_bucket_value = total_value * bucket.target_weight
        bucket_delta = target_bucket_value - bucket.current_value
        lower, upper = _rule_bounds(
            bucket.target_weight,
            config.lower_threshold,
            config.upper_threshold,
            config.mode,
        )
        bucket_status = _bucket_monitor_state(
            bucket.actual_weight,
            bucket.target_weight,
            lower,
            upper,
            config.watch_drift,
            config.warning_drift,
        )
        bucket_action = "hold"
        if bucket_delta > 0.01:
            bucket_action = "buy"
        elif bucket_delta < -0.01:
            bucket_action = "sell"

        group_details: list[GroupRebalanceDetail] = []

        for group in bucket.groups:
            target_group_value = total_value * group.target_weight
            group_delta = target_group_value - group.current_value

            group_assets = [
                a for a in all_assets
                if a.group_id == group.group_id and a.is_active and a.include_in_portfolio
            ]

            asset_actions: list[AssetAction] = []

            if plan_status == "rebalance" and abs(group_delta) > 0.01 and group_assets:
                if group_delta > 0:
                    per_asset_delta = group_delta / len(group_assets)
                    for asset in group_assets:
                        qty, _ = asset_positions.get(asset.id, (0, 0))
                        price = latest_price_for_asset(db, asset)
                        if price and price > 0:
                            shares_delta = per_asset_delta / price
                            lot_size = _determine_lot_size(asset.type, asset.exchange)
                            suggested_shares = int(shares_delta / lot_size) * lot_size
                            if suggested_shares < lot_size and lot_size > 1:
                                suggested_shares = lot_size
                            estimated = suggested_shares * price
                            asset_actions.append(AssetAction(
                                asset_id=asset.id,
                                asset_name=asset.name,
                                asset_code=asset.code,
                                current_qty=qty,
                                current_price=price,
                                current_value=qty * price,
                                action="buy",
                                target_value_delta=per_asset_delta,
                                suggested_qty_delta=shares_delta,
                                suggested_shares=suggested_shares,
                                estimated_trade_amount=round(estimated, 2),
                            ))
                        else:
                            asset_actions.append(AssetAction(
                                asset_id=asset.id,
                                asset_name=asset.name,
                                asset_code=asset.code,
                                current_qty=qty,
                                current_price=price,
                                current_value=0,
                                action="buy",
                                target_value_delta=per_asset_delta,
                                suggested_qty_delta=0,
                                suggested_shares=None,
                                estimated_trade_amount=0,
                            ))
                else:
                    total_group_value = sum(
                        asset_positions.get(a.id, (0, 0))[0] * (latest_price_for_asset(db, a) or 0)
                        for a in group_assets
                    )
                    for asset in group_assets:
                        qty, _ = asset_positions.get(asset.id, (0, 0))
                        price = latest_price_for_asset(db, asset)
                        if price and price > 0 and total_group_value > 0:
                            asset_weight = (qty * price) / total_group_value
                            sell_value = abs(group_delta) * asset_weight
                            shares_to_sell = sell_value / price
                            lot_size = _determine_lot_size(asset.type, asset.exchange)
                            suggested_shares = int(shares_to_sell / lot_size) * lot_size
                            if suggested_shares < lot_size and lot_size > 1:
                                suggested_shares = 0
                            max_sellable = int(qty / lot_size) * lot_size if lot_size > 1 else int(qty)
                            suggested_shares = min(suggested_shares, max_sellable)
                            estimated = suggested_shares * price
                            asset_actions.append(AssetAction(
                                asset_id=asset.id,
                                asset_name=asset.name,
                                asset_code=asset.code,
                                current_qty=qty,
                                current_price=price,
                                current_value=qty * price,
                                action="sell",
                                target_value_delta=group_delta * asset_weight,
                                suggested_qty_delta=-shares_to_sell,
                                suggested_shares=suggested_shares,
                                estimated_trade_amount=round(estimated, 2),
                            ))
                        else:
                            asset_actions.append(AssetAction(
                                asset_id=asset.id,
                                asset_name=asset.name,
                                asset_code=asset.code,
                                current_qty=qty,
                                current_price=price,
                                current_value=0,
                                action="hold",
                                target_value_delta=0,
                                suggested_qty_delta=0,
                                suggested_shares=None,
                                estimated_trade_amount=0,
                            ))

            group_details.append(GroupRebalanceDetail(
                group_id=group.group_id,
                group_name=group.name,
                current_value=group.current_value,
                target_value=target_group_value,
                value_delta=group_delta,
                assets=asset_actions,
            ))
            all_actions.extend(asset_actions)

        bucket_details.append(BucketRebalanceDetail(
            bucket_id=bucket.bucket_id,
            bucket_name=bucket.name,
            target_weight=bucket.target_weight,
            current_value=bucket.current_value,
            current_weight=bucket.actual_weight,
            target_value=target_bucket_value,
            value_delta=bucket_delta,
            action=bucket_action,
            lower_bound=lower,
            upper_bound=upper,
            distance_to_lower=bucket.actual_weight - lower,
            distance_to_upper=upper - bucket.actual_weight,
            monitor_state=bucket_status,
            groups=group_details,
        ))

    trade_list = sorted(
        [a for a in all_actions if a.action != "hold" and a.suggested_shares and a.suggested_shares > 0],
        key=lambda a: (0 if a.action == "sell" else 1, a.asset_name),
    )

    return RebalancePlanResponse(
        config=config,
        status=plan_status,
        status_label=_status_label(plan_status),
        status_message=_status_message(plan_status),
        triggered=plan_status == "rebalance",
        total_value=total_value,
        as_of=datetime.now(timezone.utc),
        trigger_reasons=trigger_reasons,
        price_warnings=price_warnings,
        buckets=bucket_details,
        trade_list=trade_list,
    )
