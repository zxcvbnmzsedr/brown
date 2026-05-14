from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from server.models import Instrument, InstrumentImportJob
from server.services.price_fetcher import detect_cn_fund_exchange, is_cn_exchange_traded_fund_code, normalize_code, normalize_exchange

logger = logging.getLogger(__name__)

BATCH_COMMIT_SIZE = 200


@dataclass(frozen=True)
class InstrumentSyncPayload:
    name: str
    type: str
    code: str
    exchange: str | None
    currency: str = "CNY"
    source: str | None = None


class InstrumentProvider(Protocol):
    source: str
    market: str

    def fetch(self) -> list[InstrumentSyncPayload]:
        pass


@dataclass(frozen=True)
class AkshareAStockProvider:
    source: str = "akshare_a_stock"
    market: str = "CN"

    def fetch(self) -> list[InstrumentSyncPayload]:
        import akshare as ak

        frame = ak.stock_info_a_code_name()
        instruments: list[InstrumentSyncPayload] = []
        seen: set[tuple[str, str | None]] = set()
        for row in frame.to_dict("records"):
            code = _clean(row.get("code") or row.get("代码"))
            name = _clean(row.get("name") or row.get("名称"))
            if not code or not name:
                continue
            normalized_code = normalize_code(code)
            if not normalized_code:
                continue
            exchange = _cn_exchange(normalized_code)
            key = (normalized_code, exchange)
            if key in seen:
                continue
            seen.add(key)
            instruments.append(
                InstrumentSyncPayload(
                    name=name,
                    type="stock",
                    code=normalized_code,
                    exchange=exchange,
                    currency="CNY",
                    source=self.source,
                )
            )
        return instruments


@dataclass(frozen=True)
class AkshareFundProvider:
    source: str = "akshare_fund"
    market: str = "CN"

    def fetch(self) -> list[InstrumentSyncPayload]:
        import akshare as ak

        frame = ak.fund_name_em()
        instruments: list[InstrumentSyncPayload] = []
        seen: set[str] = set()
        for row in frame.to_dict("records"):
            code = _clean(row.get("基金代码") or row.get("fund_code") or row.get("code"))
            name = _clean(row.get("基金简称") or row.get("基金名称") or row.get("name"))
            if not code or not name:
                continue
            normalized_code = normalize_code(code)
            if not normalized_code or normalized_code in seen:
                continue
            seen.add(normalized_code)
            instruments.append(
                InstrumentSyncPayload(
                    name=name,
                    type=_fund_instrument_type(name, normalized_code),
                    code=normalized_code,
                    exchange=detect_cn_fund_exchange(normalized_code),
                    currency="CNY",
                    source=self.source,
                )
            )
        return instruments


def default_instrument_providers() -> list[InstrumentProvider]:
    return [AkshareAStockProvider(), AkshareFundProvider()]


def create_instrument_sync_jobs(
    db: Session,
    sources: set[str] | None = None,
    *,
    trigger: str = "manual",
    providers: list[InstrumentProvider] | None = None,
) -> list[InstrumentImportJob]:
    jobs: list[InstrumentImportJob] = []
    for provider in providers or default_instrument_providers():
        if sources is not None and provider.source not in sources:
            continue
        job = InstrumentImportJob(
            market=provider.market,
            source=f"{provider.source}:{trigger}",
            status="pending",
            started_at=None,
            finished_at=None,
            total_count=0,
            inserted_count=0,
            updated_count=0,
            failed_count=0,
        )
        db.add(job)
        db.flush()
        jobs.append(job)
    return jobs


def run_instrument_sync_job(
    db: Session,
    job_id: int,
    *,
    providers: list[InstrumentProvider] | None = None,
) -> InstrumentImportJob:
    job = db.get(InstrumentImportJob, job_id)
    if job is None:
        raise ValueError("instrument import job not found")

    provider_source = job.source.split(":", 1)[0]
    provider = _find_provider(provider_source, providers)
    job.status = "running"
    job.started_at = datetime.now(timezone.utc)
    job.finished_at = None
    job.total_count = 0
    job.inserted_count = 0
    job.updated_count = 0
    job.failed_count = 0
    job.error_message = None
    db.flush()
    _commit_if_supported(db)

    logger.info("instrument sync job %s started: source=%s", job.id, provider_source)
    try:
        payloads = provider.fetch()
        job.total_count = len(payloads)
        db.flush()
        _commit_if_supported(db)

        for index, payload in enumerate(payloads, start=1):
            _instrument, inserted = upsert_synced_instrument(db, payload)
            if inserted:
                job.inserted_count += 1
            else:
                job.updated_count += 1

            if index % BATCH_COMMIT_SIZE == 0:
                db.flush()
                _commit_if_supported(db)
                logger.info(
                    "instrument sync job %s progress: %s/%s inserted=%s updated=%s",
                    job.id,
                    index,
                    job.total_count,
                    job.inserted_count,
                    job.updated_count,
                )

        job.status = "success"
        logger.info(
            "instrument sync job %s completed: total=%s inserted=%s updated=%s",
            job.id,
            job.total_count,
            job.inserted_count,
            job.updated_count,
        )
    except Exception as exc:
        job.status = "failed"
        job.failed_count = job.total_count or 1
        job.error_message = str(exc)
        logger.exception("instrument sync job %s failed: source=%s", job.id, provider_source)
    finally:
        job.finished_at = datetime.now(timezone.utc)
        db.flush()
        _commit_if_supported(db)
    return job


def run_instrument_sync_jobs(job_ids: list[int], providers: list[InstrumentProvider] | None = None) -> None:
    from server.db import SessionLocal

    for job_id in job_ids:
        with SessionLocal() as db:
            run_instrument_sync_job(db, job_id, providers=providers)
            db.commit()


def upsert_synced_instrument(db: Session, payload: InstrumentSyncPayload) -> tuple[Instrument, bool]:
    code = normalize_code(payload.code)
    if not code:
        raise ValueError("synced instrument code is required")
    exchange = normalize_exchange(payload.exchange) or detect_cn_fund_exchange(code)
    currency = payload.currency.upper().strip() or "CNY"
    instrument = db.scalars(
        select(Instrument)
        .where(Instrument.code == code, Instrument.exchange == exchange)
        .limit(1)
    ).first()
    if instrument is None and exchange is not None:
        instrument = db.scalars(
            select(Instrument)
            .where(Instrument.code == code, Instrument.exchange.is_(None))
            .limit(1)
        ).first()
    inserted = instrument is None
    if instrument is None:
        instrument = Instrument(
            name=payload.name,
            type=payload.type,
            code=code,
            exchange=exchange,
            currency=currency,
            source=payload.source,
            is_active=True,
        )
        db.add(instrument)
    else:
        instrument.name = payload.name
        instrument.type = payload.type
        instrument.code = code
        instrument.exchange = exchange
        instrument.currency = currency
        instrument.source = payload.source
    db.flush()
    return instrument, inserted


def _find_provider(source: str, providers: list[InstrumentProvider] | None = None) -> InstrumentProvider:
    for provider in providers or default_instrument_providers():
        if provider.source == source:
            return provider
    raise ValueError(f"unknown instrument provider: {source}")


def _commit_if_supported(db: Session) -> None:
    commit = getattr(db, "commit", None)
    if callable(commit):
        commit()


def _clean(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _cn_exchange(code: str) -> str | None:
    if code.startswith(("60", "68", "90")):
        return "SH"
    if code.startswith(("00", "30", "20")):
        return "SZ"
    if code.startswith(("43", "83", "87", "88", "92")):
        return "BJ"
    return None


def _fund_instrument_type(name: str, code: str) -> str:
    if "黄金" in name:
        return "gold"
    if is_cn_exchange_traded_fund_code(code):
        return "etf"
    return "fund"
