from __future__ import annotations

from datetime import date as Date
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


InstrumentType = Literal["stock", "fund", "etf", "bond", "gold", "crypto"]
TradingPlatformType = Literal["broker", "bank", "fund_platform", "payment", "crypto_exchange", "other"]
TransactionType = Literal["buy", "sell"]
PriceState = Literal["fresh", "stale", "missing"]


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: str | None = None


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=6, max_length=256)
    name: str | None = Field(default=None, max_length=120)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead


class AdminLoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)


class AdminUserRead(BaseModel):
    email: str


class AdminTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    admin: AdminUserRead


class TradingPlatformBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    type: TradingPlatformType
    account_type: str | None = Field(default=None, max_length=80)
    display_order: int = 0
    is_active: bool = True


class TradingPlatformCreate(TradingPlatformBase):
    pass


class TradingPlatformUpdate(TradingPlatformBase):
    pass


class TradingPlatformRead(TradingPlatformBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class TradingPlatformSeedResult(BaseModel):
    total_count: int
    inserted_count: int
    updated_count: int


class InstrumentBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    type: InstrumentType
    code: str | None = Field(default=None, max_length=64)
    exchange: str | None = Field(default=None, max_length=32)
    currency: str = Field(default="CNY", max_length=8)
    source: str | None = Field(default=None, max_length=64)
    is_active: bool = True


class InstrumentCreate(InstrumentBase):
    pass


class InstrumentUpdate(InstrumentBase):
    pass


class InstrumentRead(InstrumentBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    last_fetched_at: datetime | None = None
    latest_price: float | None = None
    price_date: Date | None = None


class InstrumentPage(BaseModel):
    items: list[InstrumentRead]
    total: int
    page: int
    page_size: int


class InstrumentSearchResult(BaseModel):
    id: str
    source: Literal["local", "akshare"]
    existing_instrument_id: int | None = None
    name: str
    type: InstrumentType
    code: str | None = None
    exchange: str | None = None
    latest_price: float | None = None


class InstrumentSyncRequest(BaseModel):
    query: str | None = Field(default=None, max_length=80)
    limit: int = Field(default=20, ge=1, le=50)


class InstrumentSyncResult(BaseModel):
    imported: int
    skipped: int
    errors: list[str] = Field(default_factory=list)


class InstrumentUniverseSyncRequest(BaseModel):
    sources: list[str] | None = None


class InstrumentImportJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    market: str
    source: str
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    total_count: int
    inserted_count: int
    updated_count: int
    failed_count: int
    error_message: str | None = None
    created_at: datetime


class InstrumentPriceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    instrument_id: int
    date: Date
    price: float
    currency: str
    fetched_at: datetime


class InstrumentPriceManualUpdate(BaseModel):
    instrument_id: int
    price: float = Field(gt=0)
    date: Date | None = None


class InstrumentPriceStatus(BaseModel):
    instrument_id: int
    instrument_name: str
    instrument_code: str | None = None
    instrument_exchange: str | None = None
    instrument_type: str
    is_configured: bool = False
    latest_price: float | None = None
    price_date: Date | None = None
    last_fetched_at: datetime | None = None
    price_age_days: int | None = None
    price_state: PriceState


class PriceStatusPage(BaseModel):
    items: list[InstrumentPriceStatus]
    total: int
    page: int
    page_size: int


class PriceFetchResult(BaseModel):
    updated: int
    target_count: int
    errors: list[str] = Field(default_factory=list)


class PortfolioGroupRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    bucket_id: int
    name: str
    target_weight: float
    display_order: int


class PortfolioBucketRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    target_weight: float
    display_order: int
    groups: list[PortfolioGroupRead] = Field(default_factory=list)


class PortfolioRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    base_currency: str
    strategy_type: str
    is_default: bool
    buckets: list[PortfolioBucketRead] = Field(default_factory=list)


class PortfolioGroupUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    target_weight: float = Field(ge=0, le=1)
    display_order: int = 0


class InvestmentAccountBase(BaseModel):
    portfolio_id: int
    trading_platform_id: int
    name: str = Field(min_length=1, max_length=120)
    is_active: bool = True


class InvestmentAccountCreate(InvestmentAccountBase):
    pass


class InvestmentAccountRead(InvestmentAccountBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    platform_name: str | None = None
    platform_type: str | None = None


class CashAccountBase(BaseModel):
    portfolio_id: int
    trading_platform_id: int | None = None
    name: str = Field(min_length=1, max_length=120)
    currency: str = Field(default="CNY", max_length=8)
    balance: float = 0
    balance_date: Date | None = None
    include_in_rebalance: bool = True
    is_active: bool = True


class CashAccountCreate(CashAccountBase):
    pass


class CashAccountUpdate(CashAccountBase):
    pass


class CashAccountRead(CashAccountBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    balance_date: Date
    platform_name: str | None = None


class UserAssetBase(BaseModel):
    portfolio_id: int
    instrument_id: int
    portfolio_group_id: int | None = None
    account_id: int | None = None
    display_name: str | None = Field(default=None, max_length=120)
    target_weight: float = Field(default=0, ge=0, le=1)
    include_in_rebalance: bool = True
    is_active: bool = True


class UserAssetCreate(UserAssetBase):
    pass


class UserAssetUpdate(UserAssetBase):
    pass


class UserAssetRead(UserAssetBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    instrument_name: str
    instrument_type: str
    instrument_code: str | None = None
    instrument_exchange: str | None = None
    group_name: str | None = None
    bucket_name: str | None = None
    account_name: str | None = None
    quantity: float = 0
    cost_basis: float = 0
    market_value: float = 0
    latest_price: float | None = None


class TransactionBase(BaseModel):
    portfolio_id: int
    instrument_id: int
    account_id: int | None = None
    cash_account_id: int | None = None
    date: Date
    type: TransactionType
    qty: float = Field(gt=0)
    price: float = Field(ge=0)
    fee: float = Field(default=0, ge=0)
    note: str | None = Field(default=None, max_length=500)


class TransactionCreate(TransactionBase):
    pass


class TransactionUpdate(TransactionBase):
    pass


class TransactionRead(TransactionBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    instrument_name: str
    instrument_code: str | None = None
    account_name: str | None = None
    cash_account_name: str | None = None
    amount: float
    created_at: datetime


class SnapshotHolding(BaseModel):
    user_asset_id: int
    instrument_id: int
    instrument_code: str | None = None
    instrument_exchange: str | None = None
    name: str
    bucket_name: str | None = None
    group_name: str | None = None
    quantity: float
    cost_basis: float
    average_cost: float
    latest_price: float | None = None
    market_value: float


class SnapshotBucket(BaseModel):
    bucket_id: int | None = None
    name: str
    target_weight: float
    current_value: float
    actual_weight: float


class PortfolioSnapshot(BaseModel):
    portfolio_id: int
    total_value: float
    holdings_value: float
    cash_value: float
    holdings: list[SnapshotHolding]
    cash_accounts: list[CashAccountRead]
    buckets: list[SnapshotBucket]
