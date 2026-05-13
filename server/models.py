from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from server.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    portfolios: Mapped[list[Portfolio]] = relationship(back_populates="user", cascade="all, delete-orphan")
    investment_accounts: Mapped[list[InvestmentAccount]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    cash_accounts: Mapped[list[CashAccount]] = relationship(back_populates="user", cascade="all, delete-orphan")
    user_assets: Mapped[list[UserAsset]] = relationship(back_populates="user", cascade="all, delete-orphan")
    transactions: Mapped[list[Transaction]] = relationship(back_populates="user", cascade="all, delete-orphan")


class TradingPlatform(Base):
    __tablename__ = "trading_platforms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    account_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    investment_accounts: Mapped[list[InvestmentAccount]] = relationship(back_populates="platform")
    cash_accounts: Mapped[list[CashAccount]] = relationship(back_populates="platform")


class Instrument(Base):
    __tablename__ = "instruments"
    __table_args__ = (UniqueConstraint("code", "exchange", name="uq_instruments_code_exchange"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    code: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    exchange: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="CNY")
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    prices: Mapped[list[InstrumentPrice]] = relationship(
        back_populates="instrument",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    user_assets: Mapped[list[UserAsset]] = relationship(back_populates="instrument")
    transactions: Mapped[list[Transaction]] = relationship(back_populates="instrument")


class InstrumentPrice(Base):
    __tablename__ = "instrument_prices"
    __table_args__ = (UniqueConstraint("instrument_id", "date", name="uq_instrument_prices_instrument_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="CNY")
    fetched_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    instrument: Mapped[Instrument] = relationship(back_populates="prices")


class InstrumentImportJob(Base):
    __tablename__ = "instrument_import_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    market: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    inserted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class Portfolio(Base):
    __tablename__ = "portfolios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    base_currency: Mapped[str] = mapped_column(String(8), nullable=False, default="CNY")
    strategy_type: Mapped[str] = mapped_column(String(64), nullable=False, default="permanent_portfolio")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    user: Mapped[User] = relationship(back_populates="portfolios")
    buckets: Mapped[list[PortfolioBucket]] = relationship(back_populates="portfolio", cascade="all, delete-orphan")
    groups: Mapped[list[PortfolioGroup]] = relationship(back_populates="portfolio", cascade="all, delete-orphan")
    investment_accounts: Mapped[list[InvestmentAccount]] = relationship(back_populates="portfolio")
    cash_accounts: Mapped[list[CashAccount]] = relationship(back_populates="portfolio")
    user_assets: Mapped[list[UserAsset]] = relationship(back_populates="portfolio")
    transactions: Mapped[list[Transaction]] = relationship(back_populates="portfolio")


class PortfolioBucket(Base):
    __tablename__ = "portfolio_buckets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    target_weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.25)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    portfolio: Mapped[Portfolio] = relationship(back_populates="buckets")
    groups: Mapped[list[PortfolioGroup]] = relationship(back_populates="bucket", cascade="all, delete-orphan")


class PortfolioGroup(Base):
    __tablename__ = "portfolio_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False, index=True)
    bucket_id: Mapped[int] = mapped_column(ForeignKey("portfolio_buckets.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    target_weight: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    portfolio: Mapped[Portfolio] = relationship(back_populates="groups")
    bucket: Mapped[PortfolioBucket] = relationship(back_populates="groups")
    user_assets: Mapped[list[UserAsset]] = relationship(back_populates="group")


class InvestmentAccount(Base):
    __tablename__ = "investment_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False, index=True)
    trading_platform_id: Mapped[int] = mapped_column(ForeignKey("trading_platforms.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    user: Mapped[User] = relationship(back_populates="investment_accounts")
    portfolio: Mapped[Portfolio] = relationship(back_populates="investment_accounts")
    platform: Mapped[TradingPlatform] = relationship(back_populates="investment_accounts")
    user_assets: Mapped[list[UserAsset]] = relationship(back_populates="account")
    transactions: Mapped[list[Transaction]] = relationship(back_populates="account")


class CashAccount(Base):
    __tablename__ = "cash_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False, index=True)
    trading_platform_id: Mapped[int | None] = mapped_column(ForeignKey("trading_platforms.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="CNY")
    balance: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    balance_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    include_in_rebalance: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    user: Mapped[User] = relationship(back_populates="cash_accounts")
    portfolio: Mapped[Portfolio] = relationship(back_populates="cash_accounts")
    platform: Mapped[TradingPlatform | None] = relationship(back_populates="cash_accounts")
    transactions: Mapped[list[Transaction]] = relationship(back_populates="cash_account")


class UserAsset(Base):
    __tablename__ = "user_assets"
    __table_args__ = (UniqueConstraint("user_id", "portfolio_id", "instrument_id", name="uq_user_assets_portfolio_instrument"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False, index=True)
    portfolio_group_id: Mapped[int | None] = mapped_column(ForeignKey("portfolio_groups.id"), nullable=True, index=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"), nullable=False, index=True)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("investment_accounts.id"), nullable=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    target_weight: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    include_in_rebalance: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    user: Mapped[User] = relationship(back_populates="user_assets")
    portfolio: Mapped[Portfolio] = relationship(back_populates="user_assets")
    group: Mapped[PortfolioGroup | None] = relationship(back_populates="user_assets")
    instrument: Mapped[Instrument] = relationship(back_populates="user_assets")
    account: Mapped[InvestmentAccount | None] = relationship(back_populates="user_assets")


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False, index=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"), nullable=False, index=True)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("investment_accounts.id"), nullable=True, index=True)
    cash_account_id: Mapped[int | None] = mapped_column(ForeignKey("cash_accounts.id"), nullable=True, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    qty: Mapped[float] = mapped_column(Float, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    fee: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    user: Mapped[User] = relationship(back_populates="transactions")
    portfolio: Mapped[Portfolio] = relationship(back_populates="transactions")
    instrument: Mapped[Instrument] = relationship(back_populates="transactions")
    account: Mapped[InvestmentAccount | None] = relationship(back_populates="transactions")
    cash_account: Mapped[CashAccount | None] = relationship(back_populates="transactions")


class SnapshotHistory(Base):
    __tablename__ = "snapshot_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False, index=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False, index=True)
    total_value: Mapped[float] = mapped_column(Float, nullable=False)
    bucket_data: Mapped[str] = mapped_column(Text, nullable=False)
    item_data: Mapped[str] = mapped_column(Text, nullable=False)
