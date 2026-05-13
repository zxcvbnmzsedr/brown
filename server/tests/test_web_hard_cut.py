from __future__ import annotations

import os
from datetime import date
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
from server.services.instrument_sync import InstrumentSyncPayload  # noqa: E402
from server.services.price_fetcher import PriceFetcher, configured_price_target_count  # noqa: E402


TODAY = date.today().isoformat()


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
        assert seeded.json()["inserted_count"] == 15
        assert seeded.json()["updated_count"] == 0

        reseeded = client.post("/admin/trading-platforms/seed-defaults", headers=headers)
        assert reseeded.status_code == 200
        assert reseeded.json()["inserted_count"] == 0
        assert reseeded.json()["updated_count"] == 15

        platforms = client.get("/admin/trading-platforms", headers=headers)
        assert platforms.status_code == 200
        names = [item["name"] for item in platforms.json()]
        assert names[:4] == ["华泰证券", "中信证券", "招商证券", "东方财富证券"]
        assert "天天基金" in names
        assert "招商银行" in names
        assert "支付宝余额宝" in names

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

        async def fetch_instrument_price(self, instrument: Instrument) -> float | None:
            self.fetched_codes.append(instrument.code)
            return 8.8

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
            assert prices == {configured_instrument_id: 8.8}

    cleanup_test_db()


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
