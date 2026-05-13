from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.db import get_db
from backend.auth import CurrentUser
from backend.schemas import RebalanceConfig, RebalancePlanResponse, RebalanceResponse
from backend.services.rebalance import compute_rebalance, compute_rebalance_plan
from backend.services.settings import get_rebalance_config, save_rebalance_config

router = APIRouter(tags=["rebalance"])

DbSession = Annotated[Session, Depends(get_db)]


@router.get("/rebalance/suggestion", response_model=RebalanceResponse)
def rebalance_suggestion(db: DbSession, current_user: CurrentUser, threshold: float = Query(default=0.15, ge=0, le=1)):
    return compute_rebalance(db, current_user.id, threshold)


@router.get("/rebalance/config", response_model=RebalanceConfig)
def get_config(db: DbSession, current_user: CurrentUser):
    return get_rebalance_config(db, current_user.id)


@router.put("/rebalance/config", response_model=RebalanceConfig)
def update_config(payload: RebalanceConfig, db: DbSession, current_user: CurrentUser):
    save_rebalance_config(db, current_user.id, payload)
    return payload


@router.get("/rebalance/plan", response_model=RebalancePlanResponse)
def rebalance_plan(db: DbSession, current_user: CurrentUser):
    return compute_rebalance_plan(db, current_user.id)
