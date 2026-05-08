from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db import Base


class PortfolioBucket(Base):
    __tablename__ = "portfolio_buckets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    target_weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.25)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    groups: Mapped[list[AssetGroup]] = relationship(
        back_populates="bucket",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class AssetGroup(Base):
    __tablename__ = "asset_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    bucket_id: Mapped[int] = mapped_column(
        ForeignKey("portfolio_buckets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    target_weight: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    bucket: Mapped[PortfolioBucket] = relationship(back_populates="groups")
    assets: Mapped[list[Asset]] = relationship(back_populates="group")


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    group_id: Mapped[int | None] = mapped_column(ForeignKey("asset_groups.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    platform: Mapped[str | None] = mapped_column(String(120), nullable=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    exchange: Mapped[str | None] = mapped_column(String(32), nullable=True)
    target_weight: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    include_in_portfolio: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    group: Mapped[AssetGroup | None] = relationship(back_populates="assets")
    transactions: Mapped[list[Transaction]] = relationship(
        back_populates="asset",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    prices: Mapped[list[PriceCache]] = relationship(
        back_populates="asset",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    qty: Mapped[float] = mapped_column(Float, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    fee: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    asset: Mapped[Asset] = relationship(back_populates="transactions")


class PriceCache(Base):
    __tablename__ = "price_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    asset: Mapped[Asset] = relationship(back_populates="prices")


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class SnapshotHistory(Base):
    __tablename__ = "snapshot_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False, index=True)
    total_value: Mapped[float] = mapped_column(Float, nullable=False)
    bucket_data: Mapped[str] = mapped_column(Text, nullable=False)  # JSON: [{name, target_weight, actual_weight, current_value}]
    item_data: Mapped[str] = mapped_column(Text, nullable=False)    # JSON: [{name, quantity, current_price, current_value, actual_weight}]


class RebalanceHistory(Base):
    __tablename__ = "rebalance_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    executed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False, index=True)
    config_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    total_value: Mapped[float] = mapped_column(Float, nullable=False)
    trigger_reasons: Mapped[str] = mapped_column(Text, nullable=False)  # JSON array
    trade_data: Mapped[str] = mapped_column(Text, nullable=False)       # JSON: [{asset_name, action, shares, amount}]
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
