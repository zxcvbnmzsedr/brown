from __future__ import annotations

import asyncio
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from backend.db import get_db
from backend.auth import CurrentUser
from backend.models import Asset, AssetGroup, PriceCache, Transaction
from backend.schemas import AssetCreate, AssetRead, AssetResolveRequest, AssetSearchResult, AssetUpdate, PriceRead, PriceUpdate
from backend.services.price_fetcher import detect_cn_exchange, normalize_code, normalize_exchange, parse_price
from backend.services.snapshot import latest_price_for_asset
from backend.routers.groups import get_group_or_404

router = APIRouter(tags=["assets"])

DbSession = Annotated[Session, Depends(get_db)]

AKSHARE_SEARCH_LIMIT = 10


def get_asset_or_404(db: Session, user_id: int, asset_id: int) -> Asset:
    asset = db.scalars(select(Asset).where(Asset.user_id == user_id, Asset.id == asset_id).limit(1)).first()
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    return asset


def asset_response(db: Session, asset: Asset) -> AssetRead:
    group = asset.group
    bucket = group.bucket if group else None
    transaction_count = (
        db.scalar(select(func.count()).select_from(Transaction).where(Transaction.asset_id == asset.id)) or 0
    )
    price_count = (
        db.scalar(select(func.count()).select_from(PriceCache).where(PriceCache.asset_id == asset.id)) or 0
    )
    return AssetRead.model_validate(asset).model_copy(
        update={
            "latest_price": latest_price_for_asset(db, asset),
            "group_name": group.name if group else None,
            "bucket_id": bucket.id if bucket else None,
            "bucket_name": bucket.name if bucket else None,
            "transaction_count": int(transaction_count),
            "price_count": int(price_count),
        }
    )


def _normalize_code(code: str | None) -> str | None:
    return normalize_code(code)


def _normalize_exchange(exchange: str | None) -> str | None:
    return normalize_exchange(exchange)


def _detect_cn_exchange(code: str | None) -> str | None:
    return detect_cn_exchange(code)


def _asset_search_id(source: str, code: str | None, exchange: str | None, name: str) -> str:
    code_part = code or "no-code"
    exchange_part = exchange or "no-exchange"
    return f"{source}:{exchange_part}:{code_part}:{name}"


def _local_asset_result(db: Session, asset: Asset) -> AssetSearchResult:
    group = asset.group
    bucket = group.bucket if group else None
    return AssetSearchResult(
        id=_asset_search_id("local", asset.code, asset.exchange, asset.name),
        source="local",
        existing_asset_id=asset.id,
        name=asset.name,
        type=asset.type,
        code=asset.code,
        exchange=asset.exchange,
        platform=asset.platform,
        latest_price=latest_price_for_asset(db, asset),
        include_in_portfolio=asset.include_in_portfolio,
        group_name=group.name if group else None,
        bucket_name=bucket.name if bucket else None,
    )


def find_existing_asset(
    db: Session,
    user_id: int,
    *,
    code: str | None,
    exchange: str | None,
    name: str | None = None,
) -> Asset | None:
    normalized_code = _normalize_code(code)
    normalized_exchange = _normalize_exchange(exchange)
    statement = select(Asset).where(Asset.user_id == user_id)
    if normalized_code:
        statement = statement.where(Asset.code == normalized_code)
        if normalized_exchange:
            statement = statement.where(Asset.exchange == normalized_exchange)
        return db.scalars(statement.limit(1)).first()

    if name:
        return db.scalars(select(Asset).where(Asset.user_id == user_id, Asset.name == name).limit(1)).first()

    return None


def create_unclassified_asset(db: Session, user_id: int, payload: AssetResolveRequest, fallback_price: float | None = None) -> Asset:
    existing = find_existing_asset(
        db,
        user_id,
        code=payload.code,
        exchange=payload.exchange,
        name=payload.name,
    )
    if existing:
        return existing

    asset = Asset(
        user_id=user_id,
        group_id=None,
        name=payload.name.strip(),
        platform=payload.platform.strip() if payload.platform else "AKShare",
        type=payload.type,
        code=_normalize_code(payload.code),
        exchange=_normalize_exchange(payload.exchange) or _detect_cn_exchange(_normalize_code(payload.code)),
        target_weight=0,
        is_active=True,
        include_in_portfolio=False,
    )
    db.add(asset)
    db.flush()

    price_value = payload.latest_price if payload.latest_price is not None and payload.latest_price > 0 else fallback_price
    if price_value is not None and price_value > 0:
        db.add(PriceCache(user_id=user_id, asset_id=asset.id, date=date.today(), price=price_value))

    return asset


def _search_local_assets(db: Session, user_id: int, query: str, limit: int) -> list[AssetSearchResult]:
    normalized_query = query.strip()
    if not normalized_query:
        return []

    like_pattern = f"%{normalized_query}%"
    assets = db.scalars(
        select(Asset)
        .options(selectinload(Asset.group).selectinload(AssetGroup.bucket))
        .where(
            Asset.user_id == user_id,
            or_(
                Asset.name.ilike(like_pattern),
                Asset.code.ilike(like_pattern),
                Asset.platform.ilike(like_pattern),
            )
        )
        .order_by(Asset.include_in_portfolio.desc(), Asset.id)
        .limit(limit)
    ).all()
    return [_local_asset_result(db, asset) for asset in assets]


def _records_from_akshare_frame(frame) -> list[dict]:
    return frame.to_dict("records")


def _extract_akshare_latest_price(record: dict) -> float | None:
    for key, value in record.items():
        name = str(key)
        if name == "最新价" or name.endswith("单位净值") or name.endswith("估算值"):
            price = parse_price(value)
            if price is not None:
                return price
    return None


def _append_akshare_records(
    *,
    query: str,
    source_type: str,
    records: list[dict],
    results: list[AssetSearchResult],
    seen: set[tuple[str | None, str | None, str]],
    limit: int,
) -> None:
    normalized_query = query.strip().lower()
    for record in records:
        code = _normalize_code(str(record.get("代码") or record.get("code") or record.get("基金代码") or ""))
        name = str(record.get("名称") or record.get("name") or record.get("基金简称") or "").strip()
        if not code or not name:
            continue

        if normalized_query not in code.lower() and normalized_query not in name.lower():
            continue

        exchange = _detect_cn_exchange(code)
        dedupe_key = (code, exchange, name)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        results.append(
            AssetSearchResult(
                id=_asset_search_id("akshare", code, exchange, name),
                source="akshare",
                name=name,
                type=source_type,
                code=code,
                exchange=exchange,
                platform="AKShare",
                latest_price=_extract_akshare_latest_price(record),
                include_in_portfolio=False,
            )
        )

        if len(results) >= limit:
            break


def _search_akshare_sync(query: str, limit: int) -> list[AssetSearchResult]:
    try:
        import akshare as ak
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AKShare 未安装，请先在 backend 环境安装 akshare",
        ) from exc

    results: list[AssetSearchResult] = []
    seen: set[tuple[str | None, str | None, str]] = set()
    errors: list[str] = []

    for fetcher_name, source_type in [
        ("stock_info_a_code_name", "stock"),
        ("fund_etf_spot_em", "fund"),
        ("fund_name_em", "fund"),
    ]:
        try:
            frame = getattr(ak, fetcher_name)()
            _append_akshare_records(
                query=query,
                source_type=source_type,
                records=_records_from_akshare_frame(frame),
                results=results,
                seen=seen,
                limit=limit,
            )
        except Exception as exc:
            errors.append(f"{fetcher_name}: {exc}")

        if len(results) >= limit:
            break

    if not results and errors:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AKShare 查询失败: {'; '.join(errors)}",
        )

    return results


def _merge_search_results(
    db: Session,
    user_id: int,
    local_results: list[AssetSearchResult],
    remote_results: list[AssetSearchResult],
    limit: int,
) -> list[AssetSearchResult]:
    merged = list(local_results)
    existing_by_market = {
        (result.code, result.exchange): result
        for result in local_results
        if result.code
    }

    for result in remote_results:
        existing = existing_by_market.get((result.code, result.exchange))
        if existing:
            continue

        existing_asset = find_existing_asset(db, user_id, code=result.code, exchange=result.exchange, name=result.name)
        if existing_asset:
            merged.append(_local_asset_result(db, existing_asset))
        else:
            merged.append(result)

        if len(merged) >= limit:
            break

    return merged[:limit]


@router.get("/assets", response_model=list[AssetRead])
def list_assets(db: DbSession, current_user: CurrentUser):
    assets = db.scalars(
        select(Asset)
        .options(selectinload(Asset.group).selectinload(AssetGroup.bucket))
        .where(Asset.user_id == current_user.id)
        .order_by(Asset.id)
    ).all()
    return [asset_response(db, asset) for asset in assets]


@router.get("/assets/search", response_model=list[AssetSearchResult])
async def search_assets(db: DbSession, current_user: CurrentUser, q: str, limit: int = AKSHARE_SEARCH_LIMIT):
    query = q.strip()
    if len(query) < 2:
        return []

    capped_limit = min(max(limit, 1), 20)
    local_results = _search_local_assets(db, current_user.id, query, capped_limit)
    if len(local_results) >= capped_limit:
        return local_results[:capped_limit]

    remote_results = await asyncio.to_thread(_search_akshare_sync, query, capped_limit)
    return _merge_search_results(db, current_user.id, local_results, remote_results, capped_limit)


@router.post("/assets", response_model=AssetRead, status_code=status.HTTP_201_CREATED)
def create_asset(payload: AssetCreate, db: DbSession, current_user: CurrentUser):
    if payload.group_id is not None:
        get_group_or_404(db, current_user.id, payload.group_id)
    asset = Asset(user_id=current_user.id, **payload.model_dump())
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset_response(db, asset)


@router.put("/assets/{asset_id}", response_model=AssetRead)
def update_asset(asset_id: int, payload: AssetUpdate, db: DbSession, current_user: CurrentUser):
    if payload.group_id is not None:
        get_group_or_404(db, current_user.id, payload.group_id)
    asset = get_asset_or_404(db, current_user.id, asset_id)
    for key, value in payload.model_dump().items():
        setattr(asset, key, value)
    db.commit()
    db.refresh(asset)
    return asset_response(db, asset)


@router.delete("/assets/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_asset(asset_id: int, db: DbSession, current_user: CurrentUser):
    asset = get_asset_or_404(db, current_user.id, asset_id)

    transaction_count = (
        db.scalar(select(func.count()).select_from(Transaction).where(Transaction.asset_id == asset.id)) or 0
    )
    if transaction_count:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"该标的已有 {transaction_count} 笔交易，无法删除。请改为停用，或先清空相关数据。",
        )

    db.delete(asset)
    db.commit()


@router.put("/prices/{asset_id}", response_model=PriceRead)
def update_price(asset_id: int, payload: PriceUpdate, db: DbSession, current_user: CurrentUser):
    asset = get_asset_or_404(db, current_user.id, asset_id)
    price_value = 1.0 if asset.type == "cash" else payload.price
    target_date = payload.date or date.today()

    existing_records = db.scalars(
                select(PriceCache)
                .where(PriceCache.user_id == current_user.id, PriceCache.asset_id == asset.id, PriceCache.date == target_date)
                .order_by(PriceCache.id)
    ).all()

    if existing_records:
        existing = existing_records[0]
        existing.price = price_value
        for duplicate in existing_records[1:]:
            db.delete(duplicate)
        db.commit()
        db.refresh(existing)
        return existing

    record = PriceCache(user_id=current_user.id, asset_id=asset.id, date=target_date, price=price_value)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
