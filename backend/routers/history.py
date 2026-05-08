from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db import get_db
from backend.models import RebalanceHistory, SnapshotHistory
from backend.schemas import RebalanceHistoryCreate, RebalanceHistoryRead, SnapshotHistoryRead
from backend.services.rebalance import compute_rebalance_plan
from backend.services.snapshot import build_snapshot

router = APIRouter(tags=["history"])

DbSession = Annotated[Session, Depends(get_db)]


@router.post("/history/snapshot", response_model=SnapshotHistoryRead, status_code=201)
def record_snapshot(db: DbSession):
    snapshot = build_snapshot(db)

    bucket_data = json.dumps([
        {
            "name": b.name,
            "target_weight": b.target_weight,
            "actual_weight": b.actual_weight,
            "current_value": b.current_value,
        }
        for b in snapshot.buckets
    ], ensure_ascii=False)

    item_data = json.dumps([
        {
            "name": i.name,
            "quantity": i.quantity,
            "current_price": i.current_price,
            "current_value": i.current_value,
            "actual_weight": i.actual_weight,
        }
        for i in snapshot.items
    ], ensure_ascii=False)

    record = SnapshotHistory(
        total_value=snapshot.total_value,
        bucket_data=bucket_data,
        item_data=item_data,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get("/history/snapshot", response_model=list[SnapshotHistoryRead])
def list_snapshots(
    db: DbSession,
    limit: int = Query(default=365, ge=1, le=1000),
):
    records = db.scalars(
        select(SnapshotHistory).order_by(SnapshotHistory.recorded_at.desc()).limit(limit)
    ).all()
    return records


@router.post("/history/rebalance", response_model=RebalanceHistoryRead, status_code=201)
def record_rebalance(payload: RebalanceHistoryCreate, db: DbSession):
    record = RebalanceHistory(
        config_mode=payload.config_mode,
        total_value=payload.total_value,
        trigger_reasons=payload.trigger_reasons,
        trade_data=payload.trade_data,
        note=payload.note,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.post("/history/rebalance/from-plan", response_model=RebalanceHistoryRead, status_code=201)
def record_rebalance_from_plan(db: DbSession):
    plan = compute_rebalance_plan(db)
    trade_data = json.dumps(
        [
            {
                "asset_id": trade.asset_id,
                "asset_name": trade.asset_name,
                "asset_code": trade.asset_code,
                "action": trade.action,
                "quantity": trade.suggested_shares,
                "amount": trade.estimated_trade_amount,
            }
            for trade in plan.trade_list
        ],
        ensure_ascii=False,
    )

    note = plan.status_message
    if plan.price_warnings:
        note = f"{note} 价格提示: {'; '.join(plan.price_warnings)}"

    record = RebalanceHistory(
        config_mode=plan.config.mode,
        total_value=plan.total_value,
        trigger_reasons=json.dumps(plan.trigger_reasons, ensure_ascii=False),
        trade_data=trade_data,
        note=note,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get("/history/rebalance", response_model=list[RebalanceHistoryRead])
def list_rebalances(
    db: DbSession,
    limit: int = Query(default=100, ge=1, le=1000),
):
    records = db.scalars(
        select(RebalanceHistory).order_by(RebalanceHistory.executed_at.desc()).limit(limit)
    ).all()
    return records
