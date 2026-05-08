from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.db import get_db
from backend.schemas import RebalanceConfig, RebalancePlanResponse, RebalanceResponse
from backend.services.rebalance import compute_rebalance, compute_rebalance_plan
from backend.services.settings import get_rebalance_config, save_rebalance_config

router = APIRouter(tags=["rebalance"])

DbSession = Annotated[Session, Depends(get_db)]


@router.get("/rebalance/suggestion", response_model=RebalanceResponse)
def rebalance_suggestion(db: DbSession, threshold: float = Query(default=0.15, ge=0, le=1)):
    return compute_rebalance(db, threshold)


@router.get("/rebalance/config", response_model=RebalanceConfig)
def get_config(db: DbSession):
    return get_rebalance_config(db)


@router.put("/rebalance/config", response_model=RebalanceConfig)
def update_config(payload: RebalanceConfig, db: DbSession):
    save_rebalance_config(db, payload)
    return payload


@router.get("/rebalance/plan", response_model=RebalancePlanResponse)
def rebalance_plan(db: DbSession):
    return compute_rebalance_plan(db)
