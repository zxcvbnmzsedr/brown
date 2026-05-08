from __future__ import annotations

import os
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = ROOT_DIR / "data" / "brown.sqlite3"
DATABASE_PATH = Path(os.getenv("BROWN_DB_PATH", DEFAULT_DB_PATH))
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@event.listens_for(engine, "connect")
def enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def init_db() -> None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    from backend import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    ensure_compatible_schema()
    seed_permanent_portfolio()


def ensure_compatible_schema() -> None:
    inspector = inspect(engine)
    if not inspector.has_table("assets"):
        return

    columns = {column["name"] for column in inspector.get_columns("assets")}
    alter_statements = []
    if "group_id" not in columns:
        alter_statements.append("ALTER TABLE assets ADD COLUMN group_id INTEGER")
    if "platform" not in columns:
        alter_statements.append("ALTER TABLE assets ADD COLUMN platform VARCHAR(120)")
    if "is_active" not in columns:
        alter_statements.append("ALTER TABLE assets ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1")
    if "include_in_portfolio" not in columns:
        alter_statements.append("ALTER TABLE assets ADD COLUMN include_in_portfolio BOOLEAN NOT NULL DEFAULT 1")
    if "last_fetched_at" not in columns:
        alter_statements.append("ALTER TABLE assets ADD COLUMN last_fetched_at DATETIME")

    if alter_statements:
        with engine.begin() as connection:
            for statement in alter_statements:
                connection.execute(text(statement))


def seed_permanent_portfolio() -> None:
    from backend.models import Asset, AssetGroup, PortfolioBucket

    defaults = [
        ("股票", 0.25, [("美股指数", 0.10), ("A股", 0.10), ("A股进攻", 0.05)]),
        ("黄金", 0.25, [("黄金", 0.25)]),
        ("债券", 0.25, [("债券", 0.25)]),
        ("现金", 0.25, [("现金", 0.25)]),
    ]

    with SessionLocal() as db:
        existing_bucket_count = db.query(PortfolioBucket).count()
        if existing_bucket_count == 0:
            for bucket_index, (bucket_name, bucket_weight, groups) in enumerate(defaults, start=1):
                bucket = PortfolioBucket(
                    name=bucket_name,
                    target_weight=bucket_weight,
                    display_order=bucket_index,
                )
                db.add(bucket)
                db.flush()
                for group_index, (group_name, group_weight) in enumerate(groups, start=1):
                    db.add(
                        AssetGroup(
                            bucket_id=bucket.id,
                            name=group_name,
                            target_weight=group_weight,
                            display_order=group_index,
                        )
                    )
            db.commit()

        groups_by_name = {group.name: group for group in db.query(AssetGroup).all()}
        changed = False
        for asset in db.query(Asset).filter(Asset.group_id.is_(None)).all():
            group_name = infer_group_name(asset.name, asset.code, asset.type)
            group = groups_by_name.get(group_name) or groups_by_name.get("A股")
            if group:
                asset.group_id = group.id
                changed = True
        if changed:
            db.commit()


def infer_group_name(name: str, code: str | None, asset_type: str) -> str:
    normalized = f"{name or ''} {code or ''}"
    if asset_type == "cash" or "现金" in normalized or "公积金" in normalized:
        return "现金"
    if "黄金" in normalized or code in {"000216", "518880"}:
        return "黄金"
    if "债" in normalized or (code or "").startswith("511") or code == "006961":
        return "债券"
    if "纳指" in normalized or "标普" in normalized or "500" in normalized:
        return "美股指数"
    if "进攻" in normalized or "化工" in normalized or "双创" in normalized:
        return "A股进攻"
    return "A股"


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
