from __future__ import annotations

import os
from datetime import date
from pathlib import Path

TEST_DB = Path(__file__).with_name("brown-test.sqlite3")
os.environ["BROWN_SKIP_DOTENV"] = "1"
os.environ.pop("DATABASE_URL", None)
os.environ["BROWN_DB_PATH"] = str(TEST_DB)
os.environ["JWT_SECRET"] = "test-user-secret"
os.environ["ADMIN_JWT_SECRET"] = "test-admin-secret"
os.environ["ADMIN_EMAIL"] = "ops@example.com"
os.environ["ADMIN_PASSWORD"] = "ops-secret"

from fastapi.testclient import TestClient  # noqa: E402

from server.app import app  # noqa: E402
from server.db import engine  # noqa: E402
from server.models import Instrument, InstrumentPrice, TradingPlatform  # noqa: E402


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
        assert instruments.json()[0]["id"] == instrument_id

        price = client.put(
            "/admin/instrument-prices/manual",
            headers=headers,
            json={"instrument_id": instrument_id, "price": 4.2, "date": TODAY},
        )
        assert price.status_code == 200
        assert price.json()["price"] == 4.2

        status = client.get("/admin/instrument-prices/status", headers=headers)
        assert status.status_code == 200
        assert status.json()[0]["latest_price"] == 4.2
        assert status.json()[0]["price_state"] == "fresh"

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
