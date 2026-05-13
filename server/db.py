from __future__ import annotations

import os
from pathlib import Path
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import event, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy import create_engine


class Base(DeclarativeBase):
    pass


ROOT_DIR = Path(__file__).resolve().parents[1]
if os.getenv("BROWN_SKIP_DOTENV") != "1":
    load_dotenv(ROOT_DIR / ".env")


def resolve_database_url() -> str:
    if database_url := os.getenv("DATABASE_URL"):
        return database_url
    if database_path := os.getenv("BROWN_DB_PATH"):
        return f"sqlite:///{Path(database_path)}"
    return "postgresql+psycopg://brown:brown@127.0.0.1:5432/brown"


DATABASE_URL = resolve_database_url()
IS_SQLITE = DATABASE_URL.startswith("sqlite")

if IS_SQLITE:
    database_path = Path(DATABASE_URL.removeprefix("sqlite:///"))
    database_path.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if IS_SQLITE else {},
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@event.listens_for(Engine, "connect")
def enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
    if not IS_SQLITE:
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def init_db() -> None:
    from server import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def seed_default_portfolio(user_id: int, db: Session | None = None) -> None:
    if db is None:
        with SessionLocal() as session:
            seed_default_portfolio(user_id, db=session)
            session.commit()
        return

    from server.models import Portfolio, PortfolioBucket, PortfolioGroup

    existing = db.scalars(select(Portfolio).where(Portfolio.user_id == user_id).limit(1)).first()
    if existing is not None:
        return

    portfolio = Portfolio(
        user_id=user_id,
        name="永久组合",
        base_currency="CNY",
        strategy_type="permanent_portfolio",
        is_default=True,
    )
    db.add(portfolio)
    db.flush()

    defaults = [
        ("股票", 0.25, [("宽基指数", 0.25)]),
        ("黄金", 0.25, [("黄金", 0.25)]),
        ("债券", 0.25, [("债券", 0.25)]),
        ("现金", 0.25, [("现金", 0.25)]),
    ]
    for bucket_index, (bucket_name, bucket_weight, groups) in enumerate(defaults, start=1):
        bucket = PortfolioBucket(
            user_id=user_id,
            portfolio_id=portfolio.id,
            name=bucket_name,
            target_weight=bucket_weight,
            display_order=bucket_index,
        )
        db.add(bucket)
        db.flush()
        for group_index, (group_name, group_weight) in enumerate(groups, start=1):
            db.add(
                PortfolioGroup(
                    user_id=user_id,
                    portfolio_id=portfolio.id,
                    bucket_id=bucket.id,
                    name=group_name,
                    target_weight=group_weight,
                    display_order=group_index,
                )
            )
    db.flush()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
