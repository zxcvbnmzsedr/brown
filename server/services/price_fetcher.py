from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
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


@dataclass(frozen=True)
class FetchedPrice:
    instrument_id: int
    date: date
    price: float
    currency: str | None = None
    source: str | None = None


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


def parse_price_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(text[:10] if fmt != "%Y%m%d" else text[:8], fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        return None


def _records_from_frame(frame: Any) -> list[dict[str, Any]]:
    if frame is None:
        return []
    empty = getattr(frame, "empty", False)
    if empty:
        return []
    if hasattr(frame, "to_dict"):
        records = frame.to_dict("records")
        return [record for record in records if isinstance(record, dict)]
    if isinstance(frame, list):
        return [record for record in frame if isinstance(record, dict)]
    return []


def _record_value(record: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in record:
            return record[key]
    return None


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

    async def fetch_cn_stock_daily_price(self, instrument: Instrument, target_date: date) -> FetchedPrice | None:
        code = normalize_code(instrument.code)
        if not _is_cn_market_code(code):
            return None
        try:
            import akshare as ak

            target = target_date.strftime("%Y%m%d")
            frame = await asyncio.to_thread(
                ak.stock_zh_a_hist,
                symbol=code,
                period="daily",
                start_date=target,
                end_date=target,
                adjust="",
            )
        except Exception as exc:
            logger.warning("Failed to fetch A-share daily close for %s: %s", code, exc)
            return None

        return self._daily_close_from_records(
            instrument=instrument,
            records=_records_from_frame(frame),
            target_date=target_date,
            source="akshare_stock_zh_a_hist",
        )

    async def fetch_cn_etf_daily_price(self, instrument: Instrument, target_date: date) -> FetchedPrice | None:
        code = normalize_code(instrument.code)
        if not _is_cn_market_code(code):
            return None
        try:
            import akshare as ak

            target = target_date.strftime("%Y%m%d")
            frame = await asyncio.to_thread(
                ak.fund_etf_hist_em,
                symbol=code,
                period="daily",
                start_date=target,
                end_date=target,
                adjust="",
            )
        except Exception as exc:
            logger.warning("Failed to fetch ETF daily close for %s: %s", code, exc)
            return None

        return self._daily_close_from_records(
            instrument=instrument,
            records=_records_from_frame(frame),
            target_date=target_date,
            source="akshare_fund_etf_hist_em",
        )

    async def fetch_cn_open_fund_nav(self, instrument: Instrument, target_date: date) -> FetchedPrice | None:
        code = normalize_code(instrument.code)
        if not code:
            return None
        try:
            import akshare as ak

            frame = await asyncio.to_thread(ak.fund_open_fund_info_em, symbol=code, indicator="单位净值走势")
        except Exception as exc:
            logger.warning("Failed to fetch open fund NAV for %s: %s", code, exc)
            return None

        best: FetchedPrice | None = None
        for record in _records_from_frame(frame):
            price_date = parse_price_date(_record_value(record, ("净值日期", "日期", "date")))
            price = parse_price(_record_value(record, ("单位净值", "净值", "nav", "NAV")))
            if price_date is None or price is None or price_date > target_date:
                continue
            if best is None or price_date > best.date:
                best = FetchedPrice(
                    instrument_id=instrument.id,
                    date=price_date,
                    price=price,
                    currency=instrument.currency,
                    source="akshare_fund_open_fund_info_em",
                )
        return best

    async def fetch_yfinance_daily_price(self, instrument: Instrument, target_date: date) -> FetchedPrice | None:
        ticker = self._yfinance_ticker(instrument)
        if not ticker:
            return None
        try:
            import yfinance as yf

            frame = await asyncio.to_thread(
                yf.Ticker(ticker).history,
                start=target_date.isoformat(),
                end=(target_date + timedelta(days=1)).isoformat(),
            )
        except Exception as exc:
            logger.warning("Failed to fetch yfinance daily close for %s: %s", ticker, exc)
            return None

        return self._daily_close_from_records(
            instrument=instrument,
            records=_records_from_frame(frame),
            target_date=target_date,
            source="yfinance",
        )

    def _daily_close_from_records(
        self,
        instrument: Instrument,
        records: list[dict[str, Any]],
        target_date: date,
        source: str,
    ) -> FetchedPrice | None:
        best: FetchedPrice | None = None
        for record in records:
            price_date = parse_price_date(_record_value(record, ("日期", "Date", "date")))
            if price_date is None:
                price_date = target_date
            price = parse_price(_record_value(record, ("收盘", "Close", "close")))
            if price_date > target_date or price is None:
                continue
            if best is None or price_date > best.date:
                best = FetchedPrice(
                    instrument_id=instrument.id,
                    date=price_date,
                    price=price,
                    currency=instrument.currency,
                    source=source,
                )
        return best

    def _yfinance_ticker(self, instrument: Instrument) -> str | None:
        code = (instrument.code or "").strip().upper()
        if not code:
            return None
        exchange = normalize_exchange(instrument.exchange)
        if exchange == "HK":
            return code if code.endswith(".HK") else f"{code.zfill(4)}.HK"
        if exchange == "SH":
            return code if code.endswith(".SS") else f"{code}.SS"
        if exchange == "SZ":
            return code if code.endswith(".SZ") else f"{code}.SZ"
        if "." in code:
            return code
        if exchange in {"US", "NASDAQ", "NYSE", "AMEX"}:
            return code
        return None

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

    async def fetch_instrument_daily_price(self, instrument: Instrument, target_date: date) -> FetchedPrice | None:
        code = normalize_code(instrument.code)
        exchange = normalize_exchange(instrument.exchange) or detect_cn_exchange(code)

        if instrument.type == "stock":
            if _is_cn_market_code(code) and exchange in {"SH", "SZ"}:
                cn_price = await self.fetch_cn_stock_daily_price(instrument, target_date)
                return cn_price or await self.fetch_yfinance_daily_price(instrument, target_date)
            return await self.fetch_yfinance_daily_price(instrument, target_date)

        if instrument.type in {"etf", "gold", "bond"} and _is_cn_market_code(code) and exchange in {"SH", "SZ"}:
            cn_price = await self.fetch_cn_etf_daily_price(instrument, target_date)
            return cn_price or await self.fetch_yfinance_daily_price(instrument, target_date)

        if instrument.type == "fund":
            return await self.fetch_cn_open_fund_nav(instrument, target_date)

        yf_price = await self.fetch_yfinance_daily_price(instrument, target_date)
        if yf_price is not None:
            return yf_price

        logger.warning("Unknown instrument daily price source for %s: type=%s exchange=%s", instrument.name, instrument.type, instrument.exchange)
        return None

    async def fetch_all_prices(self, db: Session, target_date: date | None = None) -> list[FetchedPrice]:
        instruments = db.scalars(configured_price_targets_statement()).all()
        price_date = target_date or date.today()

        results: list[FetchedPrice] = []
        for instrument in instruments:
            try:
                fetched = await self.fetch_instrument_daily_price(instrument, price_date)
            except Exception as exc:
                logger.warning("Failed to fetch daily price for instrument %s: %s", instrument.id, exc)
                fetched = None
            if fetched is not None and fetched.price > 0:
                results.append(fetched)
            await asyncio.sleep(0.3)
        return results

    def save_prices(self, db: Session, prices: list[FetchedPrice] | dict[int, float]) -> int:
        now = datetime.now(timezone.utc)
        count = 0
        for fetched in self._normalize_fetched_prices(prices):
            if fetched.price <= 0:
                continue
            instrument = db.get(Instrument, fetched.instrument_id)
            if instrument is None:
                continue
            currency = fetched.currency or instrument.currency
            existing = db.scalars(
                select(InstrumentPrice)
                .where(InstrumentPrice.instrument_id == fetched.instrument_id, InstrumentPrice.date == fetched.date)
                .order_by(InstrumentPrice.id)
            ).all()
            if existing:
                record = existing[0]
                record.price = fetched.price
                record.currency = currency
                record.fetched_at = now
                for duplicate in existing[1:]:
                    db.delete(duplicate)
            else:
                db.add(
                    InstrumentPrice(
                        instrument_id=fetched.instrument_id,
                        date=fetched.date,
                        price=fetched.price,
                        currency=currency,
                        fetched_at=now,
                    )
                )
            instrument.last_fetched_at = now
            count += 1
        db.commit()
        return count

    def _normalize_fetched_prices(self, prices: list[FetchedPrice] | dict[int, float]) -> list[FetchedPrice]:
        if isinstance(prices, dict):
            today = date.today()
            return [
                FetchedPrice(instrument_id=instrument_id, date=today, price=price)
                for instrument_id, price in prices.items()
                if price is not None
            ]
        return [price for price in prices if price is not None]
