from __future__ import annotations

import os
import sys
from calendar import monthrange
from types import SimpleNamespace
from datetime import date, timedelta
from pathlib import Path
import asyncio

TEST_DB = Path(__file__).with_name("brown-test.sqlite3")
os.environ["BROWN_SKIP_DOTENV"] = "1"
os.environ.pop("DATABASE_URL", None)
os.environ["BROWN_DB_PATH"] = str(TEST_DB)
os.environ["JWT_SECRET"] = "test-user-secret"
os.environ["ADMIN_JWT_SECRET"] = "test-admin-secret"
os.environ["ADMIN_EMAIL"] = "ops@example.com"
os.environ["ADMIN_PASSWORD"] = "ops-secret"

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from server.app import app  # noqa: E402
from server.db import SessionLocal, engine  # noqa: E402
from server.models import Instrument, InstrumentImportJob, InstrumentPrice, TradingPlatform  # noqa: E402
from server.services import instrument_sync  # noqa: E402
from server.services import price_fetcher as price_fetcher_module  # noqa: E402
from server.services.instrument_sync import InstrumentSyncPayload  # noqa: E402
from server.services.price_fetcher import PriceFetcher, configured_price_target_count  # noqa: E402


TODAY = date.today().isoformat()


class FakeFrame:
    def __init__(self, records: list[dict]) -> None:
        self.records = records
        self.empty = not records

    def to_dict(self, orient: str = "records") -> list[dict]:
        assert orient == "records"
        return self.records


def reset_test_db() -> None:
    engine.dispose()
    TEST_DB.unlink(missing_ok=True)


def cleanup_test_db() -> None:
    engine.dispose()
    TEST_DB.unlink(missing_ok=True)


def admin_headers(client: TestClient) -> dict[str, str]:
    response = client.post("/admin/auth/login", json={"email": "ops@example.com", "password": "ops-secret"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def user_headers(client: TestClient, email: str = "user@example.com") -> dict[str, str]:
    response = client.post("/auth/register", json={"email": email, "password": "secret123", "name": "User"})
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def seed_admin_catalog(client: TestClient, headers: dict[str, str]) -> tuple[int, int, int]:
    broker = client.post(
        "/admin/trading-platforms",
        headers=headers,
        json={
            "name": "华泰证券",
            "type": "broker",
            "account_type": "普通证券账户",
            "display_order": 1,
            "is_active": True,
        },
    )
    assert broker.status_code == 201
    bank = client.post(
        "/admin/trading-platforms",
        headers=headers,
        json={
            "name": "招商银行",
            "type": "bank",
            "account_type": "储蓄卡",
            "display_order": 2,
            "is_active": True,
        },
    )
    assert bank.status_code == 201
    instrument = client.post(
        "/admin/instruments",
        headers=headers,
        json={
            "name": "沪深300 ETF",
            "type": "etf",
            "code": "510300",
            "exchange": "SH",
            "currency": "CNY",
            "source": "manual",
            "is_active": True,
        },
    )
    assert instrument.status_code == 201
    return broker.json()["id"], bank.json()["id"], instrument.json()["id"]


def test_admin_auth_is_separate_from_user_auth():
    reset_test_db()

    with TestClient(app) as client:
        admin = admin_headers(client)
        user = user_headers(client)

        assert client.get("/admin/auth/me", headers=admin).status_code == 200
        assert client.get("/admin/auth/me", headers=user).status_code == 401

        created = client.post(
            "/admin/instruments",
            headers=admin,
            json={
                "name": "黄金 ETF",
                "type": "gold",
                "code": "518880",
                "exchange": "SH",
                "currency": "CNY",
                "source": "manual",
                "is_active": True,
            },
        )
        assert created.status_code == 201
        assert created.json()["latest_price"] is None

        blocked = client.post(
            "/admin/trading-platforms",
            headers=user,
            json={"name": "越权平台", "type": "broker", "account_type": None, "display_order": 0, "is_active": True},
        )
        assert blocked.status_code == 401

    cleanup_test_db()


def test_admin_catalog_and_manual_prices_are_global():
    reset_test_db()

    with TestClient(app) as client:
        headers = admin_headers(client)
        broker_id, bank_id, instrument_id = seed_admin_catalog(client, headers)
        assert broker_id != bank_id

        platforms = client.get("/admin/trading-platforms", headers=headers)
        assert platforms.status_code == 200
        assert [item["name"] for item in platforms.json()] == ["华泰证券", "招商银行"]

        instruments = client.get("/admin/instruments?q=510300", headers=headers)
        assert instruments.status_code == 200
        assert instruments.json()["items"][0]["id"] == instrument_id
        assert instruments.json()["total"] == 1

        paged = client.get("/admin/instruments?page=1&page_size=1", headers=headers)
        assert paged.status_code == 200
        assert len(paged.json()["items"]) == 1
        assert paged.json()["page_size"] == 1

        price = client.put(
            "/admin/instrument-prices/manual",
            headers=headers,
            json={"instrument_id": instrument_id, "price": 4.2, "date": TODAY},
        )
        assert price.status_code == 200
        assert price.json()["price"] == 4.2

        status = client.get("/admin/instrument-prices/status", headers=headers)
        assert status.status_code == 200
        assert status.json()["items"][0]["latest_price"] == 4.2
        assert status.json()["items"][0]["price_state"] == "fresh"
        assert status.json()["items"][0]["is_configured"] is False
        assert status.json()["total"] == 1
        assert status.json()["page_size"] == 20

        paged_status = client.get("/admin/instrument-prices/status?page=1&page_size=1", headers=headers)
        assert paged_status.status_code == 200
        assert len(paged_status.json()["items"]) == 1
        assert paged_status.json()["total"] == 1

    cleanup_test_db()


def test_admin_can_seed_common_trading_platforms():
    reset_test_db()

    with TestClient(app) as client:
        headers = admin_headers(client)
        seeded = client.post("/admin/trading-platforms/seed-defaults", headers=headers)
        assert seeded.status_code == 200
        assert seeded.json()["inserted_count"] == 30
        assert seeded.json()["updated_count"] == 0

        reseeded = client.post("/admin/trading-platforms/seed-defaults", headers=headers)
        assert reseeded.status_code == 200
        assert reseeded.json()["inserted_count"] == 0
        assert reseeded.json()["updated_count"] == 30

        platforms = client.get("/admin/trading-platforms", headers=headers)
        assert platforms.status_code == 200
        names = [item["name"] for item in platforms.json()]
        assert names[:4] == ["招商银行", "华泰证券", "中信证券", "招商证券"]
        assert "天天基金" in names
        assert "京东肯特瑞基金" in names
        assert "腾讯腾安基金" in names
        assert "支付宝余额宝" in names

    cleanup_test_db()


def test_public_instruments_are_limited_and_include_latest_price():
    reset_test_db()

    with TestClient(app) as client:
        admin = admin_headers(client)
        user = user_headers(client)
        target_id = None
        for index in range(30):
            code = f"{600000 + index}"
            name = "贵州茅台" if index == 25 else f"测试标的{index:02d}"
            created = client.post(
                "/admin/instruments",
                headers=admin,
                json={
                    "name": name,
                    "type": "stock",
                    "code": code,
                    "exchange": "SH",
                    "currency": "CNY",
                    "source": "manual",
                    "is_active": True,
                },
            )
            assert created.status_code == 201
            instrument_id = created.json()["id"]
            if name == "贵州茅台":
                target_id = instrument_id
                assert client.put(
                    "/admin/instrument-prices/manual",
                    headers=admin,
                    json={"instrument_id": instrument_id, "price": 1888.8, "date": TODAY},
                ).status_code == 200

        instruments = client.get("/instruments", headers=user)
        assert instruments.status_code == 200
        assert len(instruments.json()) == 20

        searched = client.get("/instruments?q=茅台", headers=user)
        assert searched.status_code == 200
        assert searched.json()[0]["id"] == target_id
        assert searched.json()[0]["latest_price"] == 1888.8

    cleanup_test_db()


def test_instrument_sync_job_upserts_provider_results():
    reset_test_db()

    class FakeProvider:
        source = "akshare_a_stock"
        market = "CN"

        def fetch(self):
            return [
                InstrumentSyncPayload(name="浦发银行", type="stock", code="600000", exchange="SH", source=self.source),
                InstrumentSyncPayload(name="平安银行", type="stock", code="000001", exchange="SZ", source=self.source),
            ]

    with TestClient(app):
        with SessionLocal() as db:
            jobs = instrument_sync.create_instrument_sync_jobs(db, {"akshare_a_stock"}, providers=[FakeProvider()])
            db.commit()
            assert len(jobs) == 1
            assert jobs[0].status == "pending"
            assert jobs[0].source == "akshare_a_stock:manual"

            job = instrument_sync.run_instrument_sync_job(db, jobs[0].id, providers=[FakeProvider()])
            assert job.status == "success"
            assert job.total_count == 2
            assert job.inserted_count == 2
            assert job.updated_count == 0

            rerun = instrument_sync.run_instrument_sync_job(db, jobs[0].id, providers=[FakeProvider()])
            assert rerun.status == "success"
            assert rerun.inserted_count == 0
            assert rerun.updated_count == 2

            instruments = db.scalars(select(Instrument).order_by(Instrument.code)).all()
            assert [(item.code, item.exchange, item.source) for item in instruments] == [
                ("000001", "SZ", "akshare_a_stock"),
                ("600000", "SH", "akshare_a_stock"),
            ]
            assert db.scalar(select(InstrumentImportJob).where(InstrumentImportJob.id == jobs[0].id)) is not None

    cleanup_test_db()


def test_fund_sync_classifies_exchange_traded_funds_and_open_funds():
    reset_test_db()

    class FakeProvider:
        source = "akshare_fund"
        market = "CN"

        def fetch(self):
            return [
                InstrumentSyncPayload(name="30年国债ETF鹏扬", type="etf", code="511090", exchange=None, source=self.source),
                InstrumentSyncPayload(name="短融ETF海富通", type="etf", code="511360", exchange=None, source=self.source),
                InstrumentSyncPayload(name="A500ETF华泰柏瑞", type="etf", code="563360", exchange=None, source=self.source),
                InstrumentSyncPayload(name="银华价值优选混合", type="fund", code="519001", exchange=None, source=self.source),
            ]

    with TestClient(app):
        with SessionLocal() as db:
            jobs = instrument_sync.create_instrument_sync_jobs(db, {"akshare_fund"}, providers=[FakeProvider()])
            db.commit()
            instrument_sync.run_instrument_sync_job(db, jobs[0].id, providers=[FakeProvider()])

            instruments = db.scalars(select(Instrument).order_by(Instrument.code)).all()
            assert [(item.code, item.type, item.exchange) for item in instruments] == [
                ("511090", "etf", "SH"),
                ("511360", "etf", "SH"),
                ("519001", "fund", None),
                ("563360", "etf", "SH"),
            ]

    cleanup_test_db()


def test_akshare_fund_provider_classifies_domestic_fund_codes(monkeypatch):
    def fund_name_em():
        return FakeFrame(
            [
                {"基金代码": "511090", "基金简称": "30年国债ETF鹏扬"},
                {"基金代码": "511360", "基金简称": "短融ETF海富通"},
                {"基金代码": "563360", "基金简称": "A500ETF华泰柏瑞"},
                {"基金代码": "519001", "基金简称": "银华价值优选混合"},
            ]
        )

    monkeypatch.setitem(sys.modules, "akshare", SimpleNamespace(fund_name_em=fund_name_em))

    payloads = instrument_sync.AkshareFundProvider().fetch()

    assert [(item.code, item.type, item.exchange) for item in payloads] == [
        ("511090", "etf", "SH"),
        ("511360", "etf", "SH"),
        ("563360", "etf", "SH"),
        ("519001", "fund", None),
    ]


def test_fund_sync_updates_existing_exchange_traded_fund_without_duplicate():
    reset_test_db()

    class FakeProvider:
        source = "akshare_fund"
        market = "CN"

        def fetch(self):
            return [InstrumentSyncPayload(name="30年国债ETF鹏扬", type="etf", code="511090", exchange=None, source=self.source)]

    with TestClient(app):
        with SessionLocal() as db:
            db.add(Instrument(name="30年国债ETF鹏扬", type="etf", code="511090", exchange=None, currency="CNY", source="akshare_fund"))
            db.commit()

            jobs = instrument_sync.create_instrument_sync_jobs(db, {"akshare_fund"}, providers=[FakeProvider()])
            db.commit()
            job = instrument_sync.run_instrument_sync_job(db, jobs[0].id, providers=[FakeProvider()])

            instruments = db.scalars(select(Instrument).where(Instrument.code == "511090")).all()
            assert job.inserted_count == 0
            assert job.updated_count == 1
            assert len(instruments) == 1
            assert instruments[0].exchange == "SH"

    cleanup_test_db()


def test_cn_stock_price_fetch_does_not_fallback_to_name_after_code_source_failure():
    class FakePriceFetcher(PriceFetcher):
        def __init__(self) -> None:
            super().__init__()
            self.name_fallback_called = False

        async def fetch_cn_stock(self, code: str, exchange: str) -> float | None:
            assert code == "002455"
            assert exchange == "SZ"
            return None

        async def fetch_cn_stock_by_name(self, name: str) -> float | None:
            self.name_fallback_called = True
            return 9.99

    fetcher = FakePriceFetcher()
    instrument = Instrument(name="松芝股份", type="stock", code="002455", exchange="SZ", currency="CNY", source="akshare")
    price = asyncio.run(fetcher.fetch_instrument_price(instrument))
    assert price is None
    assert fetcher.name_fallback_called is False


def test_price_fetch_only_targets_configured_user_assets():
    reset_test_db()

    class FakePriceFetcher(PriceFetcher):
        def __init__(self) -> None:
            super().__init__()
            self.fetched_codes: list[str | None] = []

        async def fetch_instrument_daily_price(self, instrument: Instrument, target_date: date):
            self.fetched_codes.append(instrument.code)
            return price_fetcher_module.FetchedPrice(instrument.id, target_date, 8.8, instrument.currency, "fake")

    with TestClient(app) as client:
        admin = admin_headers(client)
        _broker_id, _bank_id, configured_instrument_id = seed_admin_catalog(client, admin)
        unconfigured = client.post(
            "/admin/instruments",
            headers=admin,
            json={
                "name": "黄金 ETF",
                "type": "gold",
                "code": "518880",
                "exchange": "SH",
                "currency": "CNY",
                "source": "manual",
                "is_active": True,
            },
        )
        assert unconfigured.status_code == 201

        headers = user_headers(client)
        portfolios = client.get("/portfolios", headers=headers)
        assert portfolios.status_code == 200
        portfolio_id = portfolios.json()[0]["id"]

        configured = client.post(
            "/user-assets",
            headers=headers,
            json={
                "portfolio_id": portfolio_id,
                "instrument_id": configured_instrument_id,
                "portfolio_group_id": None,
                "account_id": None,
                "display_name": None,
                "target_weight": 0.25,
                "include_in_rebalance": True,
                "is_active": True,
            },
        )
        assert configured.status_code == 201

        with SessionLocal() as db:
            fetcher = FakePriceFetcher()
            prices = asyncio.run(fetcher.fetch_all_prices(db))
            assert configured_price_target_count(db) == 1
            assert fetcher.fetched_codes == ["510300"]
            assert prices == [price_fetcher_module.FetchedPrice(configured_instrument_id, date.today(), 8.8, "CNY", "fake")]

    cleanup_test_db()


def test_fetch_all_prices_carries_actual_price_date_and_keeps_fetching_after_failure():
    reset_test_db()

    class FakePriceFetcher(PriceFetcher):
        def __init__(self) -> None:
            super().__init__()
            self.fetched_codes: list[str | None] = []

        async def fetch_instrument_daily_price(self, instrument: Instrument, target_date: date):
            self.fetched_codes.append(instrument.code)
            if instrument.code == "510300":
                return price_fetcher_module.FetchedPrice(instrument.id, date(2026, 5, 11), 4.56, "CNY", "fake")
            raise RuntimeError("provider failed")

    with TestClient(app) as client:
        admin = admin_headers(client)
        _broker_id, _bank_id, configured_instrument_id = seed_admin_catalog(client, admin)
        failing = client.post(
            "/admin/instruments",
            headers=admin,
            json={
                "name": "黄金 ETF",
                "type": "gold",
                "code": "518880",
                "exchange": "SH",
                "currency": "CNY",
                "source": "manual",
                "is_active": True,
            },
        )
        assert failing.status_code == 201

        headers = user_headers(client)
        portfolio_id = client.get("/portfolios", headers=headers).json()[0]["id"]
        for instrument_id in (configured_instrument_id, failing.json()["id"]):
            configured = client.post(
                "/user-assets",
                headers=headers,
                json={
                    "portfolio_id": portfolio_id,
                    "instrument_id": instrument_id,
                    "portfolio_group_id": None,
                    "account_id": None,
                    "display_name": None,
                    "target_weight": 0.25,
                    "include_in_rebalance": True,
                    "is_active": True,
                },
            )
            assert configured.status_code == 201

        with SessionLocal() as db:
            fetcher = FakePriceFetcher()
            prices = asyncio.run(fetcher.fetch_all_prices(db, target_date=date(2026, 5, 12)))
            assert fetcher.fetched_codes == ["510300", "518880"]
            assert prices == [price_fetcher_module.FetchedPrice(configured_instrument_id, date(2026, 5, 11), 4.56, "CNY", "fake")]

            saved = fetcher.save_prices(db, prices)
            assert saved == 1
            rows = db.scalars(select(InstrumentPrice).order_by(InstrumentPrice.date)).all()
            assert [(row.instrument_id, row.date, row.price) for row in rows] == [
                (configured_instrument_id, date(2026, 5, 11), 4.56)
            ]

            updated = fetcher.save_prices(
                db,
                [price_fetcher_module.FetchedPrice(configured_instrument_id, date(2026, 5, 11), 4.78, "USD", "fake")],
            )
            assert updated == 1
            rows = db.scalars(select(InstrumentPrice)).all()
            assert len(rows) == 1
            assert rows[0].date == date(2026, 5, 11)
            assert rows[0].price == 4.78
            assert rows[0].currency == "USD"

    cleanup_test_db()


def test_akshare_daily_price_providers_parse_close_and_nav_dates(monkeypatch):
    calls: list[tuple[str, dict]] = []

    def stock_zh_a_hist(**kwargs):
        calls.append(("stock", kwargs))
        return FakeFrame([{"日期": "2026-05-12", "收盘": "12.34"}])

    def fund_etf_hist_em(**kwargs):
        calls.append(("etf", kwargs))
        return FakeFrame([{"日期": "2026-05-12", "收盘": "4.56"}])

    def fund_open_fund_info_em(**kwargs):
        calls.append(("fund", kwargs))
        return FakeFrame(
            [
                {"净值日期": "2026-05-10", "单位净值": "1.01"},
                {"净值日期": "2026-05-11", "单位净值": "1.23"},
                {"净值日期": "2026-05-13", "单位净值": "1.45"},
            ]
        )

    monkeypatch.setitem(
        sys.modules,
        "akshare",
        SimpleNamespace(
            stock_zh_a_hist=stock_zh_a_hist,
            fund_etf_hist_em=fund_etf_hist_em,
            fund_open_fund_info_em=fund_open_fund_info_em,
        ),
    )

    fetcher = PriceFetcher()
    stock = Instrument(id=1, name="浦发银行", type="stock", code="600000", exchange="SH", currency="CNY")
    etf = Instrument(id=2, name="沪深300 ETF", type="etf", code="510300", exchange="SH", currency="CNY")
    fund = Instrument(id=3, name="易方达基金", type="fund", code="110022", exchange=None, currency="CNY")

    assert asyncio.run(fetcher.fetch_instrument_daily_price(stock, date(2026, 5, 12))) == price_fetcher_module.FetchedPrice(
        1, date(2026, 5, 12), 12.34, "CNY", "akshare_stock_zh_a_hist"
    )
    assert asyncio.run(fetcher.fetch_instrument_daily_price(etf, date(2026, 5, 12))) == price_fetcher_module.FetchedPrice(
        2, date(2026, 5, 12), 4.56, "CNY", "akshare_fund_etf_hist_em"
    )
    assert asyncio.run(fetcher.fetch_instrument_daily_price(fund, date(2026, 5, 12))) == price_fetcher_module.FetchedPrice(
        3, date(2026, 5, 11), 1.23, "CNY", "akshare_fund_open_fund_info_em"
    )
    assert calls == [
        (
            "stock",
            {"symbol": "600000", "period": "daily", "start_date": "20260502", "end_date": "20260512", "adjust": ""},
        ),
        (
            "etf",
            {"symbol": "510300", "period": "daily", "start_date": "20260502", "end_date": "20260512", "adjust": ""},
        ),
        ("fund", {"symbol": "110022", "indicator": "单位净值走势"}),
    ]


def test_exchange_traded_fund_daily_price_uses_exchange_codes_without_saved_exchange(monkeypatch):
    calls: list[tuple[str, dict]] = []

    def fund_etf_hist_em(**kwargs):
        calls.append(("etf", kwargs))
        symbol = kwargs["symbol"]
        if symbol == "511090":
            return FakeFrame([{"日期": "2026-05-11", "收盘": "115.42"}, {"日期": "2026-05-13", "收盘": "115.79"}])
        if symbol == "511360":
            return FakeFrame([{"日期": "2026-05-12", "收盘": "113.45"}])
        raise AssertionError(f"unexpected ETF symbol: {symbol}")

    def fund_open_fund_info_em(**kwargs):
        calls.append(("fund", kwargs))
        return FakeFrame([{"净值日期": "2026-05-13", "单位净值": "9.99"}])

    monkeypatch.setitem(
        sys.modules,
        "akshare",
        SimpleNamespace(fund_etf_hist_em=fund_etf_hist_em, fund_open_fund_info_em=fund_open_fund_info_em),
    )

    fetcher = PriceFetcher()
    bond_etf = Instrument(id=11, name="30年国债ETF鹏扬", type="etf", code="511090", exchange=None, currency="CNY")
    short_bond_etf = Instrument(id=12, name="短融ETF海富通", type="etf", code="511360", exchange=None, currency="CNY")
    open_fund = Instrument(id=13, name="银华价值优选混合", type="fund", code="519001", exchange=None, currency="CNY")

    assert asyncio.run(fetcher.fetch_instrument_daily_price(bond_etf, date(2026, 5, 14))) == price_fetcher_module.FetchedPrice(
        11, date(2026, 5, 13), 115.79, "CNY", "akshare_fund_etf_hist_em"
    )
    assert asyncio.run(fetcher.fetch_instrument_daily_price(short_bond_etf, date(2026, 5, 14))) == price_fetcher_module.FetchedPrice(
        12, date(2026, 5, 12), 113.45, "CNY", "akshare_fund_etf_hist_em"
    )
    assert asyncio.run(fetcher.fetch_instrument_daily_price(open_fund, date(2026, 5, 14))) == price_fetcher_module.FetchedPrice(
        13, date(2026, 5, 13), 9.99, "CNY", "akshare_fund_open_fund_info_em"
    )
    assert calls == [
        (
            "etf",
            {"symbol": "511090", "period": "daily", "start_date": "20260504", "end_date": "20260514", "adjust": ""},
        ),
        (
            "etf",
            {"symbol": "511360", "period": "daily", "start_date": "20260504", "end_date": "20260514", "adjust": ""},
        ),
        ("fund", {"symbol": "519001", "indicator": "单位净值走势"}),
    ]


def test_yfinance_provider_derives_market_tickers_and_uses_close(monkeypatch):
    calls: list[tuple[str, str, str]] = []

    class FakeTicker:
        def __init__(self, ticker: str) -> None:
            self.ticker = ticker

        def history(self, start: str, end: str):
            calls.append((self.ticker, start, end))
            return FakeFrame([{"Close": "456.7"}])

    monkeypatch.setitem(sys.modules, "yfinance", SimpleNamespace(Ticker=FakeTicker))

    fetcher = PriceFetcher()
    hk = Instrument(id=7, name="腾讯控股", type="stock", code="0700", exchange="HK", currency="HKD")
    sh = Instrument(id=8, name="贵州茅台", type="stock", code="600519", exchange="SH", currency="CNY")
    sz = Instrument(id=9, name="平安银行", type="stock", code="000001", exchange="SZ", currency="CNY")

    assert asyncio.run(fetcher.fetch_yfinance_daily_price(hk, date(2026, 5, 12))) == price_fetcher_module.FetchedPrice(
        7, date(2026, 5, 12), 456.7, "HKD", "yfinance"
    )
    assert asyncio.run(fetcher.fetch_yfinance_daily_price(sh, date(2026, 5, 12))) == price_fetcher_module.FetchedPrice(
        8, date(2026, 5, 12), 456.7, "CNY", "yfinance"
    )
    assert asyncio.run(fetcher.fetch_yfinance_daily_price(sz, date(2026, 5, 12))) == price_fetcher_module.FetchedPrice(
        9, date(2026, 5, 12), 456.7, "CNY", "yfinance"
    )
    assert calls == [
        ("0700.HK", "2026-05-02", "2026-05-13"),
        ("600519.SS", "2026-05-02", "2026-05-13"),
        ("000001.SZ", "2026-05-02", "2026-05-13"),
    ]


def test_fetch_instrument_daily_price_falls_back_to_yfinance_when_cn_provider_has_no_data(monkeypatch):
    calls: list[str] = []

    class FakeTicker:
        def __init__(self, ticker: str) -> None:
            self.ticker = ticker

        def history(self, start: str, end: str):
            calls.append(self.ticker)
            return FakeFrame([{"Close": "1354.55"}])

    monkeypatch.setitem(sys.modules, "yfinance", SimpleNamespace(Ticker=FakeTicker))

    class FallbackFetcher(PriceFetcher):
        async def fetch_cn_stock_daily_price(self, instrument: Instrument, target_date: date):
            return None

    fetcher = FallbackFetcher()
    sh = Instrument(id=10, name="贵州茅台", type="stock", code="600519", exchange="SH", currency="CNY")

    assert asyncio.run(fetcher.fetch_instrument_daily_price(sh, date(2026, 5, 12))) == price_fetcher_module.FetchedPrice(
        10, date(2026, 5, 12), 1354.55, "CNY", "yfinance"
    )
    assert calls == ["600519.SS"]


def test_price_status_can_filter_configured_instruments():
    reset_test_db()

    with TestClient(app) as client:
        admin = admin_headers(client)
        _broker_id, _bank_id, configured_instrument_id = seed_admin_catalog(client, admin)
        unconfigured = client.post(
            "/admin/instruments",
            headers=admin,
            json={
                "name": "黄金 ETF",
                "type": "gold",
                "code": "518880",
                "exchange": "SH",
                "currency": "CNY",
                "source": "manual",
                "is_active": True,
            },
        )
        assert unconfigured.status_code == 201

        headers = user_headers(client)
        portfolio_id = client.get("/portfolios", headers=headers).json()[0]["id"]
        configured = client.post(
            "/user-assets",
            headers=headers,
            json={
                "portfolio_id": portfolio_id,
                "instrument_id": configured_instrument_id,
                "portfolio_group_id": None,
                "account_id": None,
                "display_name": None,
                "target_weight": 0.25,
                "include_in_rebalance": True,
                "is_active": True,
            },
        )
        assert configured.status_code == 201

        configured_status = client.get("/admin/instrument-prices/status?is_configured=true", headers=admin)
        assert configured_status.status_code == 200
        assert configured_status.json()["total"] == 1
        assert configured_status.json()["items"][0]["instrument_id"] == configured_instrument_id
        assert configured_status.json()["items"][0]["is_configured"] is True

        unconfigured_status = client.get("/admin/instrument-prices/status?is_configured=false", headers=admin)
        assert unconfigured_status.status_code == 200
        assert unconfigured_status.json()["total"] == 1
        assert unconfigured_status.json()["items"][0]["instrument_id"] == unconfigured.json()["id"]
        assert unconfigured_status.json()["items"][0]["is_configured"] is False

    cleanup_test_db()


def test_user_flow_uses_global_instrument_and_cash_account_adjustments():
    reset_test_db()

    with TestClient(app) as client:
        admin = admin_headers(client)
        broker_id, bank_id, instrument_id = seed_admin_catalog(client, admin)
        assert client.put(
            "/admin/instrument-prices/manual",
            headers=admin,
            json={"instrument_id": instrument_id, "price": 4.0, "date": TODAY},
        ).status_code == 200

        headers = user_headers(client)
        portfolios = client.get("/portfolios", headers=headers)
        assert portfolios.status_code == 200
        portfolio = portfolios.json()[0]
        portfolio_id = portfolio["id"]
        stock_group_id = next(bucket for bucket in portfolio["buckets"] if bucket["name"] == "股票")["groups"][0]["id"]

        investment_account = client.post(
            "/investment-accounts",
            headers=headers,
            json={
                "portfolio_id": portfolio_id,
                "trading_platform_id": broker_id,
                "name": "华泰普通账户",
                "is_active": True,
            },
        )
        assert investment_account.status_code == 201
        investment_account_id = investment_account.json()["id"]

        cash_account = client.post(
            "/cash-accounts",
            headers=headers,
            json={
                "portfolio_id": portfolio_id,
                "trading_platform_id": bank_id,
                "name": "招商银行现金",
                "currency": "CNY",
                "balance": 10000,
                "balance_date": TODAY,
                "include_in_rebalance": True,
                "is_active": True,
            },
        )
        assert cash_account.status_code == 201
        cash_account_id = cash_account.json()["id"]

        configured = client.post(
            "/user-assets",
            headers=headers,
            json={
                "portfolio_id": portfolio_id,
                "instrument_id": instrument_id,
                "portfolio_group_id": stock_group_id,
                "account_id": investment_account_id,
                "display_name": None,
                "target_weight": 0.25,
                "include_in_rebalance": True,
                "is_active": True,
            },
        )
        assert configured.status_code == 201

        buy = client.post(
            "/transactions",
            headers=headers,
            json={
                "portfolio_id": portfolio_id,
                "instrument_id": instrument_id,
                "account_id": investment_account_id,
                "cash_account_id": cash_account_id,
                "date": TODAY,
                "type": "buy",
                "qty": 100,
                "price": 3,
                "fee": 1,
                "note": "buy",
            },
        )
        assert buy.status_code == 201
        tx_id = buy.json()["id"]

        cash_accounts = client.get(f"/cash-accounts?portfolio_id={portfolio_id}", headers=headers)
        assert cash_accounts.status_code == 200
        assert cash_accounts.json()[0]["balance"] == 9699

        snapshot = client.get(f"/portfolios/{portfolio_id}/snapshot", headers=headers)
        assert snapshot.status_code == 200
        body = snapshot.json()
        assert body["holdings_value"] == 400
        assert body["cash_value"] == 9699
        assert body["total_value"] == 10099
        assert body["holdings"][0]["quantity"] == 100
        assert body["holdings"][0]["bucket_name"] == "股票"
        assert body["holdings"][0]["instrument_id"] == instrument_id
        assert body["holdings"][0]["instrument_code"] == "510300"
        assert body["holdings"][0]["instrument_exchange"] == "SH"

        edited = client.put(
            f"/transactions/{tx_id}",
            headers=headers,
            json={
                "portfolio_id": portfolio_id,
                "instrument_id": instrument_id,
                "account_id": investment_account_id,
                "cash_account_id": cash_account_id,
                "date": TODAY,
                "type": "buy",
                "qty": 50,
                "price": 3,
                "fee": 1,
                "note": "edit",
            },
        )
        assert edited.status_code == 200
        cash_accounts = client.get(f"/cash-accounts?portfolio_id={portfolio_id}", headers=headers)
        assert cash_accounts.json()[0]["balance"] == 9849

        deleted = client.delete(f"/transactions/{tx_id}", headers=headers)
        assert deleted.status_code == 204
        cash_accounts = client.get(f"/cash-accounts?portfolio_id={portfolio_id}", headers=headers)
        assert cash_accounts.json()[0]["balance"] == 10000

    cleanup_test_db()


def test_portfolio_trend_recalculates_holdings_and_cash_from_history():
    reset_test_db()

    with TestClient(app) as client:
        day0 = date.today() - timedelta(days=4)
        day1 = date.today() - timedelta(days=3)
        day2 = date.today() - timedelta(days=2)
        day4 = date.today()
        admin = admin_headers(client)
        broker_id, bank_id, instrument_id = seed_admin_catalog(client, admin)
        for price_date, price in (
            (day0.isoformat(), 2.0),
            (day2.isoformat(), 4.0),
        ):
            assert client.put(
                "/admin/instrument-prices/manual",
                headers=admin,
                json={"instrument_id": instrument_id, "price": price, "date": price_date},
            ).status_code == 200

        headers = user_headers(client)
        other_headers = user_headers(client, email="other@example.com")
        portfolio_id = client.get("/portfolios", headers=headers).json()[0]["id"]
        other_portfolio_id = client.get("/portfolios", headers=other_headers).json()[0]["id"]

        investment_account = client.post(
            "/investment-accounts",
            headers=headers,
            json={
                "portfolio_id": portfolio_id,
                "trading_platform_id": broker_id,
                "name": "华泰普通账户",
                "is_active": True,
            },
        )
        assert investment_account.status_code == 201
        investment_account_id = investment_account.json()["id"]

        cash_account = client.post(
            "/cash-accounts",
            headers=headers,
            json={
                "portfolio_id": portfolio_id,
                "trading_platform_id": bank_id,
                "name": "招商银行现金",
                "currency": "CNY",
                "balance": 1000,
                "balance_date": day4.isoformat(),
                "include_in_rebalance": True,
                "is_active": True,
            },
        )
        assert cash_account.status_code == 201
        cash_account_id = cash_account.json()["id"]

        configured = client.post(
            "/user-assets",
            headers=headers,
            json={
                "portfolio_id": portfolio_id,
                "instrument_id": instrument_id,
                "portfolio_group_id": None,
                "account_id": investment_account_id,
                "display_name": None,
                "target_weight": 0.25,
                "include_in_rebalance": True,
                "is_active": True,
            },
        )
        assert configured.status_code == 201

        linked_buy = client.post(
            "/transactions",
            headers=headers,
            json={
                "portfolio_id": portfolio_id,
                "instrument_id": instrument_id,
                "account_id": investment_account_id,
                "cash_account_id": cash_account_id,
                "date": day1.isoformat(),
                "type": "buy",
                "qty": 10,
                "price": 3,
                "fee": 1,
                "note": "linked",
            },
        )
        assert linked_buy.status_code == 201

        unlinked_buy = client.post(
            "/transactions",
            headers=headers,
            json={
                "portfolio_id": portfolio_id,
                "instrument_id": instrument_id,
                "account_id": investment_account_id,
                "cash_account_id": None,
                "date": day2.isoformat(),
                "type": "buy",
                "qty": 5,
                "price": 4,
                "fee": 0,
                "note": "unlinked",
            },
        )
        assert unlinked_buy.status_code == 201

        trend = client.get(f"/portfolios/{portfolio_id}/trend?days=7", headers=headers)
        assert trend.status_code == 200
        body = trend.json()
        assert body["portfolio_id"] == portfolio_id
        assert len(body["points"]) == 7
        assert body["start_date"] <= day0.isoformat()
        assert body["end_date"] >= day2.isoformat()

        by_date = {point["date"]: point for point in body["points"]}
        assert by_date[day0.isoformat()]["holdings_value"] == 0
        assert by_date[day0.isoformat()]["cash_value"] == 1000
        assert by_date[day1.isoformat()]["holdings_value"] == 20
        assert by_date[day1.isoformat()]["cash_value"] == 969
        assert by_date[day2.isoformat()]["holdings_value"] == 60
        assert by_date[day2.isoformat()]["cash_value"] == 969
        assert by_date[day2.isoformat()]["total_value"] == 1029
        assert body["summary"]["end_value"] == body["points"][-1]["total_value"]
        assert body["summary"]["change_value"] == body["summary"]["end_value"] - body["summary"]["start_value"]

        blocked = client.get(f"/portfolios/{other_portfolio_id}/trend", headers=headers)
        assert blocked.status_code == 404

    cleanup_test_db()


def test_profit_calendar_summarizes_daily_asset_changes_and_transactions():
    reset_test_db()

    with TestClient(app) as client:
        day0 = date.today() - timedelta(days=4)
        day1 = date.today() - timedelta(days=3)
        day2 = date.today() - timedelta(days=2)
        admin = admin_headers(client)
        broker_id, bank_id, instrument_id = seed_admin_catalog(client, admin)
        for price_date, price in (
            (day0.isoformat(), 2.0),
            (day1.isoformat(), 3.0),
            (day2.isoformat(), 4.0),
        ):
            assert client.put(
                "/admin/instrument-prices/manual",
                headers=admin,
                json={"instrument_id": instrument_id, "price": price, "date": price_date},
            ).status_code == 200

        headers = user_headers(client)
        other_headers = user_headers(client, email="calendar-other@example.com")
        portfolio_id = client.get("/portfolios", headers=headers).json()[0]["id"]
        other_portfolio_id = client.get("/portfolios", headers=other_headers).json()[0]["id"]

        investment_account = client.post(
            "/investment-accounts",
            headers=headers,
            json={
                "portfolio_id": portfolio_id,
                "trading_platform_id": broker_id,
                "name": "华泰普通账户",
                "is_active": True,
            },
        )
        assert investment_account.status_code == 201
        investment_account_id = investment_account.json()["id"]

        cash_account = client.post(
            "/cash-accounts",
            headers=headers,
            json={
                "portfolio_id": portfolio_id,
                "trading_platform_id": bank_id,
                "name": "招商银行现金",
                "currency": "CNY",
                "balance": 1000,
                "balance_date": date.today().isoformat(),
                "include_in_rebalance": True,
                "is_active": True,
            },
        )
        assert cash_account.status_code == 201
        cash_account_id = cash_account.json()["id"]

        assert client.post(
            "/user-assets",
            headers=headers,
            json={
                "portfolio_id": portfolio_id,
                "instrument_id": instrument_id,
                "portfolio_group_id": None,
                "account_id": investment_account_id,
                "display_name": None,
                "target_weight": 0.25,
                "include_in_rebalance": True,
                "is_active": True,
            },
        ).status_code == 201

        assert client.post(
            "/transactions",
            headers=headers,
            json={
                "portfolio_id": portfolio_id,
                "instrument_id": instrument_id,
                "account_id": investment_account_id,
                "cash_account_id": cash_account_id,
                "date": day1.isoformat(),
                "type": "buy",
                "qty": 10,
                "price": 3,
                "fee": 1,
                "note": "linked",
            },
        ).status_code == 201
        assert client.post(
            "/transactions",
            headers=headers,
            json={
                "portfolio_id": portfolio_id,
                "instrument_id": instrument_id,
                "account_id": investment_account_id,
                "cash_account_id": None,
                "date": day2.isoformat(),
                "type": "buy",
                "qty": 5,
                "price": 4,
                "fee": 0,
                "note": "unlinked",
            },
        ).status_code == 201

        calendar = client.get(
            f"/portfolios/{portfolio_id}/profit-calendar?year={day1.year}&month={day1.month}",
            headers=headers,
        )
        assert calendar.status_code == 200
        body = calendar.json()
        assert body["portfolio_id"] == portfolio_id
        assert body["year"] == day1.year
        assert body["month"] == day1.month
        assert len(body["days"]) == monthrange(day1.year, day1.month)[1]

        by_date = {day["date"]: day for day in body["days"]}
        assert by_date[day1.isoformat()]["change_value"] == -1
        assert by_date[day1.isoformat()]["buy_amount"] == 31
        assert by_date[day1.isoformat()]["fee"] == 1
        assert by_date[day1.isoformat()]["transaction_count"] == 1
        assert by_date[day2.isoformat()]["change_value"] == 30
        assert by_date[day2.isoformat()]["buy_amount"] == 20
        assert by_date[day2.isoformat()]["transaction_count"] == 1
        assert body["summary"]["positive_days"] >= 1
        assert body["summary"]["negative_days"] >= 1
        assert body["summary"]["buy_amount"] == 51
        assert body["summary"]["fee"] == 1

        blocked = client.get(
            f"/portfolios/{other_portfolio_id}/profit-calendar?year={day1.year}&month={day1.month}",
            headers=headers,
        )
        assert blocked.status_code == 404

    cleanup_test_db()


def test_user_cannot_create_instruments_and_cash_is_not_an_instrument():
    reset_test_db()

    with TestClient(app) as client:
        headers = user_headers(client)
        blocked = client.post(
            "/admin/instruments",
            headers=headers,
            json={
                "name": "现金",
                "type": "cash",
                "code": None,
                "exchange": None,
                "currency": "CNY",
                "source": "manual",
                "is_active": True,
            },
        )
        assert blocked.status_code == 401

        with engine.connect() as conn:
            assert conn.execute(TradingPlatform.__table__.select()).fetchall() == []
            assert conn.execute(Instrument.__table__.select()).fetchall() == []
            assert conn.execute(InstrumentPrice.__table__.select()).fetchall() == []

    cleanup_test_db()
