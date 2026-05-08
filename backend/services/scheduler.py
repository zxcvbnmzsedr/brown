from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def _fetch_all_prices_job() -> None:
    from backend.db import SessionLocal
    from backend.services.price_fetcher import PriceFetcher

    logger.info("Scheduled price fetch started")
    fetcher = PriceFetcher()
    try:
        with SessionLocal() as db:
            prices = await fetcher.fetch_all_prices(db)
            count = fetcher.save_prices(db, prices)
            logger.info("Scheduled price fetch completed: %d assets updated", count)
    except Exception as e:
        logger.error("Scheduled price fetch failed: %s", e)
    finally:
        await fetcher.close()


def start_scheduler() -> None:
    @scheduler.scheduled_job("cron", hour=16, minute=30, day_of_week="mon-fri", id="cn_prices")
    async def fetch_cn_prices():
        await _fetch_all_prices_job()

    @scheduler.scheduled_job("cron", hour=5, minute=0, day_of_week="tue-sat", id="us_hk_prices")
    async def fetch_us_hk_prices():
        await _fetch_all_prices_job()

    scheduler.start()
    logger.info("Price scheduler started")


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Price scheduler stopped")
