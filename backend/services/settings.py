from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import Setting
from backend.schemas import RebalanceConfig


def get_setting(db: Session, key: str, default: str | None = None) -> str | None:
    setting = db.scalars(select(Setting).where(Setting.key == key).limit(1)).first()
    if setting:
        return setting.value
    return default


def set_setting(db: Session, key: str, value: str) -> None:
    existing = db.scalars(select(Setting).where(Setting.key == key).limit(1)).first()
    if existing:
        existing.value = value
    else:
        db.add(Setting(key=key, value=value))
    db.commit()


def get_rebalance_config(db: Session) -> RebalanceConfig:
    raw = get_setting(db, "rebalance_config")
    if raw:
        try:
            data = json.loads(raw)
            return RebalanceConfig(**data)
        except (json.JSONDecodeError, ValueError):
            pass
    return RebalanceConfig()


def save_rebalance_config(db: Session, config: RebalanceConfig) -> None:
    set_setting(db, "rebalance_config", config.model_dump_json())
