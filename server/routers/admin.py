from __future__ import annotations

import asyncio
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from server.auth import CurrentAdmin, admin_email, authenticate_admin, create_admin_access_token
from server.db import get_db
from server.models import Instrument, InstrumentImportJob, InstrumentPrice, TradingPlatform, UserAsset
from server.schemas import (
    AdminLoginRequest,
    AdminTokenResponse,
    AdminUserRead,
    InstrumentCreate,
    InstrumentImportJobRead,
    InstrumentPage,
    InstrumentPriceManualUpdate,
    InstrumentPriceRead,
    InstrumentPriceStatus,
    InstrumentRead,
    InstrumentSyncRequest,
    InstrumentSyncResult,
    InstrumentUniverseSyncRequest,
    InstrumentUpdate,
    PriceFetchResult,
    PriceStatusPage,
    TradingPlatformCreate,
    TradingPlatformRead,
    TradingPlatformSeedResult,
    TradingPlatformUpdate,
)
from server.services.portfolio import latest_price_record_for_instrument
from server.services.price_fetcher import (
    PriceFetcher,
    configured_price_target_count,
    detect_cn_exchange,
    normalize_code,
    normalize_exchange,
    parse_price,
)
from server.services import instrument_sync
from server.services.trading_platforms import seed_default_trading_platforms

router = APIRouter(prefix="/admin", tags=["admin"])

DbSession = Annotated[Session, Depends(get_db)]


def instrument_response(db: Session, instrument: Instrument) -> InstrumentRead:
    price_record = latest_price_record_for_instrument(db, instrument.id)
    return InstrumentRead.model_validate(instrument).model_copy(
        update={
            "latest_price": price_record.price if price_record else None,
            "price_date": price_record.date if price_record else None,
        }
    )


def get_instrument_or_404(db: Session, instrument_id: int) -> Instrument:
    instrument = db.get(Instrument, instrument_id)
    if instrument is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instrument not found")
    return instrument


def get_platform_or_404(db: Session, platform_id: int) -> TradingPlatform:
    platform = db.get(TradingPlatform, platform_id)
    if platform is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trading platform not found")
    return platform


def normalize_instrument(instrument: Instrument) -> None:
    instrument.code = normalize_code(instrument.code)
    instrument.exchange = normalize_exchange(instrument.exchange) or detect_cn_exchange(instrument.code)
    instrument.currency = instrument.currency.upper().strip() or "CNY"


@router.post("/auth/login", response_model=AdminTokenResponse)
def admin_login(payload: AdminLoginRequest):
    if not authenticate_admin(payload.email, payload.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="管理员邮箱或密码不正确")
    email = admin_email()
    return AdminTokenResponse(access_token=create_admin_access_token(email), admin=AdminUserRead(email=email))


@router.get("/auth/me", response_model=AdminUserRead)
def admin_me(current_admin: CurrentAdmin):
    return AdminUserRead(email=current_admin)


@router.get("/trading-platforms", response_model=list[TradingPlatformRead])
def list_trading_platforms(db: DbSession, _admin: CurrentAdmin, include_inactive: bool = True):
    statement = select(TradingPlatform)
    if not include_inactive:
        statement = statement.where(TradingPlatform.is_active == True)
    return db.scalars(statement.order_by(TradingPlatform.display_order, TradingPlatform.id)).all()


@router.post("/trading-platforms", response_model=TradingPlatformRead, status_code=status.HTTP_201_CREATED)
def create_trading_platform(payload: TradingPlatformCreate, db: DbSession, _admin: CurrentAdmin):
    platform = TradingPlatform(**payload.model_dump())
    db.add(platform)
    db.commit()
    db.refresh(platform)
    return platform


@router.post("/trading-platforms/seed-defaults", response_model=TradingPlatformSeedResult)
def seed_trading_platforms(db: DbSession, _admin: CurrentAdmin):
    result = seed_default_trading_platforms(db)
    db.commit()
    return result


@router.put("/trading-platforms/{platform_id}", response_model=TradingPlatformRead)
def update_trading_platform(platform_id: int, payload: TradingPlatformUpdate, db: DbSession, _admin: CurrentAdmin):
    platform = get_platform_or_404(db, platform_id)
    for key, value in payload.model_dump().items():
        setattr(platform, key, value)
    db.commit()
    db.refresh(platform)
    return platform


@router.post("/trading-platforms/{platform_id}/toggle", response_model=TradingPlatformRead)
def toggle_trading_platform(platform_id: int, db: DbSession, _admin: CurrentAdmin):
    platform = get_platform_or_404(db, platform_id)
    platform.is_active = not platform.is_active
    db.commit()
    db.refresh(platform)
    return platform


@router.get("/instruments", response_model=InstrumentPage)
def list_instruments(
    db: DbSession,
    _admin: CurrentAdmin,
    q: str | None = None,
    instrument_type: str | None = None,
    market: str | None = None,
    include_inactive: bool = True,
    page: int = 1,
    page_size: int = 20,
):
    statement = select(Instrument)
    if not include_inactive:
        statement = statement.where(Instrument.is_active == True)
    if instrument_type:
        statement = statement.where(Instrument.type == instrument_type)
    if market:
        statement = statement.where(Instrument.exchange == market.upper())
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        statement = statement.where(or_(Instrument.name.ilike(pattern), Instrument.code.ilike(pattern)))
    safe_page = max(page, 1)
    safe_page_size = min(max(page_size, 1), 100)
    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    instruments = db.scalars(
        statement
        .order_by(Instrument.is_active.desc(), Instrument.id)
        .offset((safe_page - 1) * safe_page_size)
        .limit(safe_page_size)
    ).all()
    return InstrumentPage(
        items=[instrument_response(db, instrument) for instrument in instruments],
        total=int(total),
        page=safe_page,
        page_size=safe_page_size,
    )


@router.post("/instruments", response_model=InstrumentRead, status_code=status.HTTP_201_CREATED)
def create_instrument(payload: InstrumentCreate, db: DbSession, _admin: CurrentAdmin):
    instrument = Instrument(**payload.model_dump())
    normalize_instrument(instrument)
    db.add(instrument)
    db.commit()
    db.refresh(instrument)
    return instrument_response(db, instrument)


@router.put("/instruments/{instrument_id}", response_model=InstrumentRead)
def update_instrument(instrument_id: int, payload: InstrumentUpdate, db: DbSession, _admin: CurrentAdmin):
    instrument = get_instrument_or_404(db, instrument_id)
    for key, value in payload.model_dump().items():
        setattr(instrument, key, value)
    normalize_instrument(instrument)
    db.commit()
    db.refresh(instrument)
    return instrument_response(db, instrument)


@router.post("/instruments/{instrument_id}/toggle", response_model=InstrumentRead)
def toggle_instrument(instrument_id: int, db: DbSession, _admin: CurrentAdmin):
    instrument = get_instrument_or_404(db, instrument_id)
    instrument.is_active = not instrument.is_active
    db.commit()
    db.refresh(instrument)
    return instrument_response(db, instrument)


@router.get("/instruments/import-jobs", response_model=list[InstrumentImportJobRead])
def list_instrument_import_jobs(db: DbSession, _admin: CurrentAdmin, limit: int = 20):
    safe_limit = min(max(limit, 1), 100)
    return db.scalars(
        select(InstrumentImportJob)
        .order_by(InstrumentImportJob.id.desc())
        .limit(safe_limit)
    ).all()


@router.post("/instruments/sync-jobs", response_model=list[InstrumentImportJobRead])
def create_instrument_sync_jobs(
    background_tasks: BackgroundTasks,
    db: DbSession,
    _admin: CurrentAdmin,
    payload: InstrumentUniverseSyncRequest | None = None,
):
    source_filter = set(payload.sources) if payload and payload.sources else None
    jobs = instrument_sync.create_instrument_sync_jobs(db, source_filter)
    db.commit()
    background_tasks.add_task(instrument_sync.run_instrument_sync_jobs, [job.id for job in jobs])
    return jobs


def _instrument_type_from_record(name: str, code: str | None) -> str:
    if "黄金" in name:
        return "gold"
    if code and code.startswith(("51", "15", "16")):
        return "etf"
    if code and code.startswith(("0", "1", "5")):
        return "fund"
    return "stock"


def _append_akshare_records(query: str, records: list[dict], results: list[dict], seen: set[str], limit: int) -> None:
    for record in records:
        if len(results) >= limit:
            return
        code = normalize_code(str(record.get("代码") or record.get("基金代码") or record.get("symbol") or ""))
        name = str(record.get("名称") or record.get("基金简称") or record.get("name") or "").strip()
        if not code or not name:
            continue
        exchange = normalize_exchange(str(record.get("市场") or "")) or detect_cn_exchange(code)
        key = f"{exchange or ''}:{code}:{name}"
        if key in seen:
            continue
        seen.add(key)
        results.append(
            {
                "id": f"akshare:{key}",
                "source": "akshare",
                "existing_instrument_id": None,
                "name": name,
                "type": _instrument_type_from_record(name, code),
                "code": code,
                "exchange": exchange,
                "latest_price": parse_price(record.get("最新价") or record.get("单位净值") or record.get("最新净值")),
            }
        )


def _search_akshare_sync(query: str, limit: int) -> list[dict]:
    try:
        import akshare as ak
    except ImportError:
        return []

    results: list[dict] = []
    seen: set[str] = set()
    providers = [
        lambda: ak.fund_name_em(),
        lambda: ak.stock_zh_a_spot_em(),
    ]
    for provider in providers:
        if len(results) >= limit:
            break
        try:
            records = provider().to_dict("records")
        except Exception:
            continue
        filtered = [
            record
            for record in records
            if query in str(record.get("代码") or record.get("基金代码") or record.get("symbol") or "")
            or query in str(record.get("名称") or record.get("基金简称") or record.get("name") or "")
        ]
        _append_akshare_records(query, filtered, results, seen, limit)
    return results


@router.post("/instruments/sync", response_model=InstrumentSyncResult)
async def sync_instruments(payload: InstrumentSyncRequest, db: DbSession, _admin: CurrentAdmin):
    query = (payload.query or "").strip()
    if len(query) < 2:
        return InstrumentSyncResult(imported=0, skipped=0, errors=["请输入至少 2 个字符用于同步标的。"])

    remote_results = await asyncio.to_thread(_search_akshare_sync, query, payload.limit)
    imported = 0
    skipped = 0
    for result in remote_results:
        existing = db.scalars(
            select(Instrument)
            .where(Instrument.code == result["code"], Instrument.exchange == result["exchange"])
            .limit(1)
        ).first()
        if existing is not None:
            skipped += 1
            continue
        instrument = Instrument(
            name=result["name"],
            type=result["type"],
            code=result["code"],
            exchange=result["exchange"],
            currency="CNY",
            source="AKShare",
            is_active=True,
        )
        db.add(instrument)
        db.flush()
        if result["latest_price"]:
            db.add(InstrumentPrice(instrument_id=instrument.id, date=date.today(), price=result["latest_price"], currency="CNY"))
        imported += 1
    db.commit()
    return InstrumentSyncResult(imported=imported, skipped=skipped)


@router.get("/instrument-prices/status", response_model=PriceStatusPage)
def list_price_status(
    db: DbSession,
    _admin: CurrentAdmin,
    q: str | None = None,
    price_state: str | None = None,
    is_configured: bool | None = None,
    page: int = 1,
    page_size: int = 20,
):
    safe_page = max(page, 1)
    safe_page_size = min(max(page_size, 1), 100)
    today = date.today()
    fresh_since = today - timedelta(days=7)
    latest_price_dates = (
        select(InstrumentPrice.instrument_id, func.max(InstrumentPrice.date).label("date"))
        .group_by(InstrumentPrice.instrument_id)
        .subquery()
    )
    configured_instrument_ids = (
        select(UserAsset.instrument_id)
        .where(UserAsset.is_active == True)
        .distinct()
        .subquery()
    )
    statement = (
        select(Instrument, InstrumentPrice, configured_instrument_ids.c.instrument_id.is_not(None).label("is_configured"))
        .outerjoin(configured_instrument_ids, configured_instrument_ids.c.instrument_id == Instrument.id)
        .outerjoin(latest_price_dates, latest_price_dates.c.instrument_id == Instrument.id)
        .outerjoin(
            InstrumentPrice,
            (InstrumentPrice.instrument_id == Instrument.id)
            & (InstrumentPrice.date == latest_price_dates.c.date),
        )
    )
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        statement = statement.where(or_(Instrument.name.ilike(pattern), Instrument.code.ilike(pattern)))
    if price_state == "missing":
        statement = statement.where(InstrumentPrice.id.is_(None))
    elif price_state == "stale":
        statement = statement.where(InstrumentPrice.date < fresh_since)
    elif price_state == "fresh":
        statement = statement.where(InstrumentPrice.date >= fresh_since)
    if is_configured is True:
        statement = statement.where(configured_instrument_ids.c.instrument_id.is_not(None))
    elif is_configured is False:
        statement = statement.where(configured_instrument_ids.c.instrument_id.is_(None))

    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    records = db.execute(
        statement
        .order_by(Instrument.is_active.desc(), Instrument.id)
        .offset((safe_page - 1) * safe_page_size)
        .limit(safe_page_size)
    ).all()

    rows: list[InstrumentPriceStatus] = []
    for instrument, price_record, configured in records:
        age_days = None if price_record is None else max((today - price_record.date).days, 0)
        if price_record is None:
            state = "missing"
        elif age_days is not None and age_days > 7:
            state = "stale"
        else:
            state = "fresh"
        rows.append(
            InstrumentPriceStatus(
                instrument_id=instrument.id,
                instrument_name=instrument.name,
                instrument_code=instrument.code,
                instrument_exchange=instrument.exchange,
                instrument_type=instrument.type,
                is_configured=bool(configured),
                latest_price=price_record.price if price_record else None,
                price_date=price_record.date if price_record else None,
                last_fetched_at=instrument.last_fetched_at,
                price_age_days=age_days,
                price_state=state,
            )
        )
    return PriceStatusPage(items=rows, total=int(total), page=safe_page, page_size=safe_page_size)


@router.put("/instrument-prices/manual", response_model=InstrumentPriceRead)
def update_price(payload: InstrumentPriceManualUpdate, db: DbSession, _admin: CurrentAdmin):
    instrument = get_instrument_or_404(db, payload.instrument_id)
    target_date = payload.date or date.today()
    record = db.scalars(
        select(InstrumentPrice)
        .where(InstrumentPrice.instrument_id == instrument.id, InstrumentPrice.date == target_date)
        .limit(1)
    ).first()
    if record:
        record.price = payload.price
        record.currency = instrument.currency
    else:
        record = InstrumentPrice(
            instrument_id=instrument.id,
            date=target_date,
            price=payload.price,
            currency=instrument.currency,
        )
        db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.post("/instrument-prices/fetch", response_model=PriceFetchResult)
async def fetch_prices(db: DbSession, _admin: CurrentAdmin):
    fetcher = PriceFetcher()
    try:
        prices = await fetcher.fetch_all_prices(db)
        updated = fetcher.save_prices(db, prices)
        return PriceFetchResult(updated=updated, target_count=configured_price_target_count(db), errors=[])
    except Exception as exc:
        return PriceFetchResult(updated=0, target_count=0, errors=[str(exc)])
    finally:
        await fetcher.close()
