from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import date, datetime, timezone
from difflib import SequenceMatcher
from typing import Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from server.models import Instrument, InstrumentPrice, UserAsset

logger = logging.getLogger(__name__)

EASTMONEY_FUND_URL = "https://fundgz.1234567.com.cn/js/{code}.js"
EASTMONEY_STOCK_URL = "https://push2.eastmoney.com/api/qt/ulist.np/get?fltt=2&secids={secid}&fields=f12,f13,f14,f2"
EASTMONEY_SEARCH_URL = "https://searchapi.eastmoney.com/api/suggest/get"
EASTMONEY_SEARCH_TOKEN = "44c9d251add88e27b65ed86506f6e5da"


def normalize_code(code: str | None) -> str | None:
    if not code:
        return None
    normalized = code.strip().upper()
    if "." in normalized:
        normalized = normalized.split(".")[-1]
    return normalized or None


def normalize_exchange(exchange: str | None) -> str | None:
    if not exchange:
        return None
    normalized = exchange.strip().upper()
    aliases = {
        "SSE": "SH",
        "SHSE": "SH",
        "XSHG": "SH",
        "SZSE": "SZ",
        "XSHE": "SZ",
    }
    return aliases.get(normalized, normalized)


def detect_cn_exchange(code: str | None) -> str | None:
    if not code:
        return None
    normalized = normalize_code(code)
    if not normalized or not _is_cn_market_code(normalized):
        return None
    if normalized.startswith(("5", "6", "9")):
        return "SH"
    if normalized.startswith(("0", "1", "2", "3")):
        return "SZ"
    return None


def _is_cn_market_code(code: str | None) -> bool:
    return bool(code and code.isdigit() and len(code) == 6)


def parse_price(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if not text or text in {"-", "--", "---", "nan", "None"}:
        return None
    try:
        price = float(text)
    except (TypeError, ValueError):
        return None
    return price if price > 0 else None


def _normalize_name(value: str | None) -> str:
    return (value or "").replace(" ", "").replace("　", "").strip().lower()


def _name_score(query: str, candidate: str) -> float:
    normalized_query = _normalize_name(query)
    normalized_candidate = _normalize_name(candidate)
    if not normalized_query or not normalized_candidate:
        return 0
    if normalized_query == normalized_candidate:
        return 1
    if normalized_query in normalized_candidate or normalized_candidate in normalized_query:
        return 0.9
    return SequenceMatcher(None, normalized_query, normalized_candidate).ratio()


def configured_price_targets_statement():
    configured_ids = (
        select(UserAsset.instrument_id)
        .where(UserAsset.is_active == True)
        .distinct()
        .subquery()
    )
    return (
        select(Instrument)
        .join(configured_ids, configured_ids.c.instrument_id == Instrument.id)
        .where(Instrument.is_active == True)
        .order_by(Instrument.id)
    )


def configured_price_target_count(db: Session) -> int:
    return int(
        db.scalar(
            select(func.count(func.distinct(UserAsset.instrument_id)))
            .join(Instrument, Instrument.id == UserAsset.instrument_id)
            .where(UserAsset.is_active == True, Instrument.is_active == True)
        )
        or 0
    )


class PriceFetcher:
    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=15.0)
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def fetch_cn_fund(self, code: str) -> float | None:
        normalized_code = normalize_code(code)
        if not normalized_code:
            return None

        client = await self._get_client()
        try:
            resp = await client.get(EASTMONEY_FUND_URL.format(code=normalized_code))
            resp.raise_for_status()
            match = re.search(r"jsonpgz\((.+)\)", resp.text)
            if not match:
                return None
            data = json.loads(match.group(1))
            return parse_price(data.get("gsz")) or parse_price(data.get("dwjz"))
        except Exception as exc:
            logger.error("Failed to fetch CN fund %s: %s", normalized_code, exc)
            return None

    async def fetch_cn_stock(self, code: str, exchange: str) -> float | None:
        normalized_code = normalize_code(code)
        normalized_exchange = normalize_exchange(exchange)
        if not _is_cn_market_code(normalized_code) or normalized_exchange not in {"SH", "SZ"}:
            return None
        prefix = "1" if normalized_exchange == "SH" else "0"
        quote = await self.fetch_eastmoney_quote(f"{prefix}.{normalized_code}")
        if not quote or quote["code"] != normalized_code:
            return None
        return quote["price"]

    async def fetch_eastmoney_quote(self, secid: str) -> dict[str, Any] | None:
        client = await self._get_client()
        try:
            resp = await client.get(
                EASTMONEY_STOCK_URL.format(secid=secid),
                headers={"Referer": "https://quote.eastmoney.com/"},
            )
            resp.raise_for_status()
            records = resp.json().get("data", {}).get("diff", [])
            if not records:
                return None
            record = records[0]
            price = parse_price(record.get("f2"))
            code = normalize_code(str(record.get("f12") or ""))
            name = str(record.get("f14") or "").strip()
            return {"code": code, "name": name, "price": price} if code and price is not None else None
        except Exception as exc:
            logger.warning("EastMoney quote unavailable for %s: %s", secid, exc)
            return None

    async def search_eastmoney_quotes(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        client = await self._get_client()
        try:
            resp = await client.get(
                EASTMONEY_SEARCH_URL,
                params={"input": query, "type": "14", "token": EASTMONEY_SEARCH_TOKEN, "count": limit},
                headers={"Referer": "https://quote.eastmoney.com/"},
            )
            resp.raise_for_status()
            records = resp.json().get("QuotationCodeTable", {}).get("Data") or []
        except Exception as exc:
            logger.warning("EastMoney quote search unavailable for %s: %s", query, exc)
            return []

        results: list[dict[str, Any]] = []
        for record in records:
            quote_id = str(record.get("QuoteID") or "")
            code = normalize_code(str(record.get("Code") or record.get("UnifiedCode") or ""))
            name = str(record.get("Name") or "").strip()
            classify = str(record.get("Classify") or "")
            security_type = str(record.get("SecurityTypeName") or "")
            if quote_id and code and name:
                results.append(
                    {
                        "secid": quote_id,
                        "code": code,
                        "name": name,
                        "classify": classify,
                        "security_type": security_type,
                    }
                )
        return results

    async def fetch_cn_stock_by_name(self, name: str) -> float | None:
        candidates = await self.search_eastmoney_quotes(name)
        best_score = 0.0
        best_secid: str | None = None
        for candidate in candidates:
            if candidate["classify"] != "AStock":
                continue
            score = _name_score(name, candidate["name"])
            if score > best_score:
                best_score = score
                best_secid = candidate["secid"]
        if best_score < 0.72 or not best_secid:
            return None
        quote = await self.fetch_eastmoney_quote(best_secid)
        return quote["price"] if quote else None

    async def fetch_cn_etf_by_name(self, name: str) -> float | None:
        candidates = await self.search_eastmoney_quotes(name)
        best_score = 0.0
        best_secid: str | None = None
        for candidate in candidates:
            if candidate["classify"] not in {"Fund", "OTCFUND"}:
                continue
            score = _name_score(name, candidate["name"])
            if score > best_score:
                best_score = score
                best_secid = candidate["secid"]
        if best_score < 0.72 or not best_secid:
            return None
        quote = await self.fetch_eastmoney_quote(best_secid)
        return quote["price"] if quote else None

    async def fetch_instrument_price(self, instrument: Instrument) -> float | None:
        code = normalize_code(instrument.code)
        exchange = normalize_exchange(instrument.exchange) or detect_cn_exchange(code)
        attempted_known_source = False

        if _is_cn_market_code(code) and exchange in {"SH", "SZ"}:
            attempted_known_source = True
            market_price = await self.fetch_cn_stock(code, exchange)
            if market_price is not None:
                return market_price
            if instrument.type == "stock":
                logger.info(
                    "No price fetched for CN stock %s(%s.%s) from EastMoney",
                    instrument.name,
                    exchange,
                    code,
                )
                return None

        if code and instrument.type in {"fund", "etf"}:
            attempted_known_source = True
            fund_price = await self.fetch_cn_fund(code)
            if fund_price is not None:
                return fund_price

        if instrument.type in {"fund", "etf", "gold", "bond"}:
            attempted_known_source = True
            etf_price = await self.fetch_cn_etf_by_name(instrument.name)
            if etf_price is not None:
                return etf_price

        if instrument.type == "stock":
            attempted_known_source = True
            stock_price = await self.fetch_cn_stock_by_name(instrument.name)
            if stock_price is not None:
                return stock_price

        if not attempted_known_source:
            logger.warning("Unknown instrument quote source for %s: type=%s exchange=%s", instrument.name, instrument.type, instrument.exchange)
        return None

    async def fetch_all_prices(self, db: Session) -> dict[int, float]:
        instruments = db.scalars(configured_price_targets_statement()).all()

        results: dict[int, float] = {}
        for instrument in instruments:
            price = await self.fetch_instrument_price(instrument)
            if price is not None and price > 0:
                results[instrument.id] = price
            await asyncio.sleep(0.3)
        return results

    def save_prices(self, db: Session, prices: dict[int, float]) -> int:
        today = date.today()
        now = datetime.now(timezone.utc)
        count = 0
        for instrument_id, price in prices.items():
            instrument = db.get(Instrument, instrument_id)
            if instrument is None:
                continue
            existing = db.scalars(
                select(InstrumentPrice)
                .where(InstrumentPrice.instrument_id == instrument_id, InstrumentPrice.date == today)
                .order_by(InstrumentPrice.id)
            ).all()
            if existing:
                record = existing[0]
                record.price = price
                record.currency = instrument.currency
                record.fetched_at = now
                for duplicate in existing[1:]:
                    db.delete(duplicate)
            else:
                db.add(
                    InstrumentPrice(
                        instrument_id=instrument_id,
                        date=today,
                        price=price,
                        currency=instrument.currency,
                        fetched_at=now,
                    )
                )
            instrument.last_fetched_at = now
            count += 1
        db.commit()
        return count
