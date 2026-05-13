from __future__ import annotations

from datetime import date as Date
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


AssetType = Literal["stock", "fund", "money_market", "cash", "crypto"]
TransactionType = Literal["buy", "sell"]
PriceState = Literal["fresh", "stale", "missing", "cash"]
MonitorState = Literal["ok", "watch", "warning", "rebalance", "incomplete"]


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: str | None = None


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead


class AssetBase(BaseModel):
    group_id: int | None = None
    name: str = Field(min_length=1, max_length=120)
    platform: str | None = Field(default=None, max_length=120)
    type: AssetType
    code: str | None = Field(default=None, max_length=64)
    exchange: str | None = Field(default=None, max_length=32)
    target_weight: float = Field(default=0, ge=0, le=1)
    is_active: bool = True
    include_in_portfolio: bool = True


class AssetCreate(AssetBase):
    pass


class AssetUpdate(AssetBase):
    pass


class AssetRead(AssetBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    latest_price: float | None = None
    group_name: str | None = None
    bucket_id: int | None = None
    bucket_name: str | None = None
    transaction_count: int = 0
    price_count: int = 0


class AssetSearchResult(BaseModel):
    id: str
    source: Literal["local", "akshare"]
    existing_asset_id: int | None = None
    name: str
    type: AssetType
    code: str | None = None
    exchange: str | None = None
    platform: str | None = None
    latest_price: float | None = None
    include_in_portfolio: bool = False
    group_name: str | None = None
    bucket_name: str | None = None


class AssetResolveRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    type: AssetType
    code: str | None = Field(default=None, max_length=64)
    exchange: str | None = Field(default=None, max_length=32)
    platform: str | None = Field(default=None, max_length=120)
    latest_price: float | None = Field(default=None, ge=0)


class BucketBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    target_weight: float = Field(ge=0, le=1)
    display_order: int = 0


class BucketCreate(BucketBase):
    pass


class BucketUpdate(BucketBase):
    pass


class GroupBase(BaseModel):
    bucket_id: int
    name: str = Field(min_length=1, max_length=120)
    target_weight: float = Field(default=0, ge=0, le=1)
    display_order: int = 0


class GroupCreate(GroupBase):
    pass


class GroupUpdate(GroupBase):
    pass


class GroupRead(GroupBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    bucket_name: str | None = None


class BucketRead(BucketBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    groups: list[GroupRead] = Field(default_factory=list)


class PriceUpdate(BaseModel):
    price: float = Field(ge=0)
    date: Date | None = None


class PriceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    asset_id: int
    date: Date
    price: float
    fetched_at: datetime


class TransactionBase(BaseModel):
    date: Date
    type: TransactionType
    qty: float = Field(gt=0)
    price: float = Field(ge=0)
    fee: float = Field(default=0, ge=0)
    note: str | None = Field(default=None, max_length=500)


class TransactionCreate(TransactionBase):
    asset_id: int | None = None
    asset: AssetResolveRequest | None = None


class TransactionUpdate(BaseModel):
    date: Date | None = None
    type: TransactionType | None = None
    asset_id: int | None = None
    qty: float | None = Field(default=None, gt=0)
    price: float | None = Field(default=None, ge=0)
    fee: float | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=500)


class TransactionRead(TransactionBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    asset_id: int
    created_at: datetime
    asset_name: str


class OpeningPositionBase(BaseModel):
    asset_id: int
    date: Date
    qty: float = Field(gt=0)
    cost_price: float = Field(ge=0)
    current_price: float = Field(ge=0)
    note: str | None = Field(default=None, max_length=500)


class OpeningPositionCreate(OpeningPositionBase):
    pass


class OpeningPositionUpdate(BaseModel):
    asset_id: int | None = None
    date: Date | None = None
    qty: float | None = Field(default=None, gt=0)
    cost_price: float | None = Field(default=None, ge=0)
    current_price: float | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=500)


class OpeningPositionRead(OpeningPositionBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    asset_name: str
    asset_code: str | None = None
    asset_exchange: str | None = None
    include_in_portfolio: bool


class SnapshotItem(BaseModel):
    asset_id: int
    bucket_id: int | None
    bucket_name: str | None
    group_id: int | None
    group_name: str | None
    include_in_portfolio: bool
    name: str
    platform: str | None
    type: str
    code: str | None
    exchange: str | None
    target_weight: float
    quantity: float
    cost_basis: float
    average_cost: float | None
    current_price: float | None
    price_date: Date | None = None
    price_fetched_at: datetime | None = None
    price_age_days: int | None = None
    price_state: PriceState = "missing"
    current_value: float
    actual_weight: float
    drift: float


class SnapshotGroup(BaseModel):
    group_id: int
    bucket_id: int
    name: str
    target_weight: float
    current_value: float
    actual_weight: float
    drift: float


class SnapshotBucket(BaseModel):
    bucket_id: int
    name: str
    target_weight: float
    current_value: float
    actual_weight: float
    drift: float
    lower_bound: float | None = None
    upper_bound: float | None = None
    distance_to_lower: float | None = None
    distance_to_upper: float | None = None
    monitor_state: MonitorState = "ok"
    groups: list[SnapshotGroup] = Field(default_factory=list)


class SnapshotResponse(BaseModel):
    as_of: datetime
    total_value: float
    total_holdings_value: float = 0
    target_weight_total: float
    price_state: MonitorState = "ok"
    stale_price_count: int = 0
    missing_price_count: int = 0
    pending_classification_count: int = 0
    pending_classification_value: float = 0
    buckets: list[SnapshotBucket]
    items: list[SnapshotItem]
    all_items: list[SnapshotItem] = Field(default_factory=list)


class RebalanceSuggestion(BaseModel):
    scope: Literal["bucket"]
    bucket_id: int
    name: str
    action: Literal["buy", "sell"]
    drift: float
    target_value: float
    current_value: float
    amount: float
    candidate_assets: list[str]


class RebalanceResponse(BaseModel):
    threshold: float
    triggered: bool
    total_value: float
    suggestions: list[RebalanceSuggestion]


# --- Phase 3: Enhanced Rebalance Schemas ---


class RebalanceConfig(BaseModel):
    mode: Literal["classic_35_15", "custom"] = "classic_35_15"
    upper_threshold: float = Field(default=0.35, ge=0, le=1)
    lower_threshold: float = Field(default=0.15, ge=0, le=1)
    watch_drift: float = Field(default=0.05, ge=0, le=1)
    warning_drift: float = Field(default=0.10, ge=0, le=1)
    max_price_age_days: int = Field(default=7, ge=0, le=365)


class AssetAction(BaseModel):
    asset_id: int
    asset_name: str
    asset_code: str | None
    current_qty: float
    current_price: float | None
    current_value: float
    action: Literal["buy", "sell", "hold"]
    target_value_delta: float
    suggested_qty_delta: float
    suggested_shares: int | None
    estimated_trade_amount: float


class GroupRebalanceDetail(BaseModel):
    group_id: int
    group_name: str
    current_value: float
    target_value: float
    value_delta: float
    assets: list[AssetAction]


class BucketRebalanceDetail(BaseModel):
    bucket_id: int
    bucket_name: str
    target_weight: float
    current_value: float
    current_weight: float
    target_value: float
    value_delta: float
    action: Literal["buy", "sell", "hold"]
    lower_bound: float
    upper_bound: float
    distance_to_lower: float
    distance_to_upper: float
    monitor_state: MonitorState
    groups: list[GroupRebalanceDetail]


class RebalancePlanResponse(BaseModel):
    config: RebalanceConfig
    status: MonitorState
    status_label: str
    status_message: str
    triggered: bool
    total_value: float
    as_of: datetime
    trigger_reasons: list[str]
    price_warnings: list[str] = Field(default_factory=list)
    buckets: list[BucketRebalanceDetail]
    trade_list: list[AssetAction]


# --- Phase 5: History & Export Schemas ---


class SnapshotHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    recorded_at: datetime
    total_value: float
    bucket_data: str  # JSON string
    item_data: str    # JSON string


class RebalanceHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    executed_at: datetime
    config_mode: str
    total_value: float
    trigger_reasons: str  # JSON string
    trade_data: str       # JSON string
    note: str | None = None


class RebalanceHistoryCreate(BaseModel):
    config_mode: str
    total_value: float
    trigger_reasons: str
    trade_data: str
    note: str | None = None


class CsvExportRow(BaseModel):
    date: str
    asset_name: str
    asset_code: str | None
    type: TransactionType
    qty: float
    price: float
    fee: float
    note: str | None
