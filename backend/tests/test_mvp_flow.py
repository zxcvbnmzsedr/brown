from __future__ import annotations

import os
from pathlib import Path
from datetime import date

TEST_DB = Path(__file__).with_name("brown-test.sqlite3")
os.environ["BROWN_DB_PATH"] = str(TEST_DB)

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from backend.app import app  # noqa: E402
from backend.db import engine  # noqa: E402
from backend.models import PriceCache  # noqa: E402
from backend.routers import assets as assets_router  # noqa: E402
from backend.services.price_fetcher import PriceFetcher  # noqa: E402


TODAY = date.today().isoformat()


def reset_test_db() -> None:
    engine.dispose()
    TEST_DB.unlink(missing_ok=True)


def cleanup_test_db() -> None:
    engine.dispose()
    TEST_DB.unlink(missing_ok=True)


def asset_payload(
    *,
    group_id: int | None,
    name: str,
    asset_type: str = "fund",
    code: str | None = None,
    exchange: str | None = None,
    include_in_portfolio: bool = True,
) -> dict:
    return {
        "group_id": group_id,
        "name": name,
        "platform": "测试账户",
        "type": asset_type,
        "code": code,
        "exchange": exchange,
        "target_weight": 0,
        "is_active": True,
        "include_in_portfolio": include_in_portfolio,
    }


def test_mvp_portfolio_flow():
    reset_test_db()

    with TestClient(app) as client:
        structure = client.get("/portfolio/structure")
        assert structure.status_code == 200
        buckets = {bucket["name"]: bucket for bucket in structure.json()}
        assert set(buckets) == {"股票", "黄金", "债券", "现金"}
        cash_group_id = buckets["现金"]["groups"][0]["id"]
        gold_group_id = buckets["黄金"]["groups"][0]["id"]

        cash = client.post(
            "/assets",
            json={
                "group_id": cash_group_id,
                "name": "现金",
                "platform": "小罐罐",
                "type": "cash",
                "code": None,
                "exchange": None,
                "target_weight": 0.25,
                "is_active": True,
                "include_in_portfolio": True,
            },
        )
        assert cash.status_code == 201

        gold = client.post(
            "/assets",
            json={
                "group_id": gold_group_id,
                "name": "黄金 ETF",
                "platform": "涨乐",
                "type": "fund",
                "code": "518880",
                "exchange": "SH",
                "target_weight": 0.75,
                "is_active": True,
                "include_in_portfolio": True,
            },
        )
        assert gold.status_code == 201

        cash_id = cash.json()["id"]
        gold_id = gold.json()["id"]

        price = client.put(f"/prices/{gold_id}", json={"price": 10, "date": TODAY})
        assert price.status_code == 200

        assert client.post(
            "/transactions",
            json={
                "date": TODAY,
                "asset_id": cash_id,
                "type": "buy",
                "qty": 1000,
                "price": 1,
                "fee": 0,
                "note": "init",
            },
        ).status_code == 201
        assert client.post(
            "/transactions",
            json={
                "date": TODAY,
                "asset_id": gold_id,
                "type": "buy",
                "qty": 50,
                "price": 8,
                "fee": 0,
                "note": "init",
            },
        ).status_code == 201

        snapshot = client.get("/portfolio/snapshot")
        assert snapshot.status_code == 200
        body = snapshot.json()
        assert body["total_value"] == 1500
        assert body["price_state"] == "ok"
        assert len(body["items"]) == 2
        assert len(body["buckets"]) == 4
        gold_bucket = next(bucket for bucket in body["buckets"] if bucket["name"] == "黄金")
        assert gold_bucket["current_value"] == 500
        assert gold_bucket["lower_bound"] == 0.15
        assert gold_bucket["upper_bound"] == 0.35
        assert gold_bucket["monitor_state"] == "watch"

        rebalance = client.get("/rebalance/suggestion")
        assert rebalance.status_code == 200
        assert rebalance.json()["triggered"] is True
        assert rebalance.json()["suggestions"][0]["scope"] == "bucket"

        plan = client.get("/rebalance/plan")
        assert plan.status_code == 200
        assert plan.json()["status"] == "rebalance"
        assert plan.json()["triggered"] is True
        assert plan.json()["trigger_reasons"]
        assert len(plan.json()["trade_list"]) > 0

        recorded = client.post("/history/rebalance/from-plan")
        assert recorded.status_code == 201
        assert recorded.json()["config_mode"] == "classic_35_15"
        assert recorded.json()["trade_data"] != "[]"

        oversell = client.post(
            "/transactions",
            json={
                "date": TODAY,
                "asset_id": gold_id,
                "type": "sell",
                "qty": 1000,
                "price": 10,
                "fee": 0,
                "note": "too much",
            },
        )
        assert oversell.status_code == 400

    cleanup_test_db()


def test_rebalance_plan_blocks_when_prices_are_missing():
    reset_test_db()

    with TestClient(app) as client:
        structure = client.get("/portfolio/structure")
        assert structure.status_code == 200
        buckets = {bucket["name"]: bucket for bucket in structure.json()}
        stock_group_id = buckets["股票"]["groups"][0]["id"]
        cash_group_id = buckets["现金"]["groups"][0]["id"]

        stock = client.post(
            "/assets",
            json={
                "group_id": stock_group_id,
                "name": "纳指 ETF",
                "platform": "券商",
                "type": "fund",
                "code": "513100",
                "exchange": "SH",
                "target_weight": 0,
                "is_active": True,
                "include_in_portfolio": True,
            },
        )
        cash = client.post(
            "/assets",
            json={
                "group_id": cash_group_id,
                "name": "现金",
                "platform": "账户",
                "type": "cash",
                "code": None,
                "exchange": None,
                "target_weight": 0,
                "is_active": True,
                "include_in_portfolio": True,
            },
        )
        assert stock.status_code == 201
        assert cash.status_code == 201

        stock_id = stock.json()["id"]
        cash_id = cash.json()["id"]

        assert client.post(
            "/transactions",
            json={
                "date": TODAY,
                "asset_id": stock_id,
                "type": "buy",
                "qty": 100,
                "price": 10,
                "fee": 0,
                "note": "init",
            },
        ).status_code == 201
        assert client.post(
            "/transactions",
            json={
                "date": TODAY,
                "asset_id": cash_id,
                "type": "buy",
                "qty": 100,
                "price": 1,
                "fee": 0,
                "note": "init",
            },
        ).status_code == 201

        plan = client.get("/rebalance/plan")
        assert plan.status_code == 200
        body = plan.json()
        assert body["status"] == "incomplete"
        assert body["triggered"] is False
        assert body["trade_list"] == []
        assert body["price_warnings"] == ["纳指 ETF缺少价格"]

    cleanup_test_db()


def test_price_fetch_infers_cn_exchange_and_updates_existing_daily_record(monkeypatch):
    reset_test_db()

    async def fake_stock_price(self, code: str, exchange: str):
        assert code == "600926"
        assert exchange == "SH"
        return 7.32

    monkeypatch.setattr(PriceFetcher, "fetch_cn_stock", fake_stock_price)

    with TestClient(app) as client:
        structure = client.get("/portfolio/structure")
        assert structure.status_code == 200
        stock_group_id = next(bucket for bucket in structure.json() if bucket["name"] == "股票")["groups"][0]["id"]

        asset = client.post(
            "/assets",
            json=asset_payload(
                group_id=stock_group_id,
                name="北京银行",
                asset_type="fund",
                code="600926",
                exchange=None,
            ),
        )
        assert asset.status_code == 201
        asset_id = asset.json()["id"]
        assert client.put(f"/prices/{asset_id}", json={"price": 7.0, "date": TODAY}).status_code == 200

        fetched = client.post(f"/prices/fetch/{asset_id}")
        assert fetched.status_code == 200
        assert fetched.json() == {"updated": 1, "errors": []}

        assets = client.get("/assets").json()
        updated_asset = next(item for item in assets if item["id"] == asset_id)
        assert updated_asset["latest_price"] == 7.32

        with Session(engine) as db:
            records = db.query(PriceCache).filter(PriceCache.asset_id == asset_id).all()
            assert len(records) == 1

    cleanup_test_db()


def test_price_fetch_falls_back_to_name_when_code_is_invalid(monkeypatch):
    reset_test_db()

    async def missing_stock_price(self, code: str, exchange: str):
        raise AssertionError("invalid five digit code should not call direct market fetch")

    async def missing_fund_price(self, code: str):
        return None

    async def fake_stock_by_name(self, name: str):
        assert name == "北京银行"
        return 6.11

    monkeypatch.setattr(PriceFetcher, "fetch_cn_stock", missing_stock_price)
    monkeypatch.setattr(PriceFetcher, "fetch_cn_fund", missing_fund_price)
    monkeypatch.setattr(PriceFetcher, "fetch_cn_stock_by_name", fake_stock_by_name)

    with TestClient(app) as client:
        structure = client.get("/portfolio/structure")
        assert structure.status_code == 200
        stock_group_id = next(bucket for bucket in structure.json() if bucket["name"] == "股票")["groups"][0]["id"]

        asset = client.post(
            "/assets",
            json=asset_payload(
                group_id=stock_group_id,
                name="北京银行",
                asset_type="stock",
                code="45401",
                exchange=None,
            ),
        )
        assert asset.status_code == 201

        fetched = client.post(f"/prices/fetch/{asset.json()['id']}")
        assert fetched.status_code == 200
        assert fetched.json() == {"updated": 1, "errors": []}

    cleanup_test_db()


def test_akshare_records_include_latest_price():
    results: list[assets_router.AssetSearchResult] = []
    assets_router._append_akshare_records(
        query="518880",
        source_type="fund",
        records=[{"代码": "518880", "名称": "黄金ETF华安", "最新价": "9.88"}],
        results=results,
        seen=set(),
        limit=10,
    )

    assert len(results) == 1
    assert results[0].latest_price == 9.88
    assert results[0].exchange == "SH"


def test_transaction_can_create_pending_asset_then_classify_it(monkeypatch):
    reset_test_db()

    def fake_search(query: str, limit: int):
        assert query == "600519"
        assert limit == 10
        return [
            assets_router.AssetSearchResult(
                id="akshare:SH:600519:贵州茅台",
                source="akshare",
                name="贵州茅台",
                type="stock",
                code="600519",
                exchange="SH",
                platform="AKShare",
                latest_price=None,
                include_in_portfolio=False,
            )
        ]

    monkeypatch.setattr(assets_router, "_search_akshare_sync", fake_search)

    with TestClient(app) as client:
        search = client.get("/assets/search", params={"q": "600519"})
        assert search.status_code == 200
        result = search.json()[0]
        assert result["source"] == "akshare"
        assert result["existing_asset_id"] is None

        created = client.post(
            "/transactions",
            json={
                "date": TODAY,
                "asset": {
                    "name": result["name"],
                    "type": result["type"],
                    "code": result["code"],
                    "exchange": result["exchange"],
                    "platform": result["platform"],
                    "latest_price": result["latest_price"],
                },
                "type": "buy",
                "qty": 1,
                "price": 1700,
                "fee": 0,
                "note": "new asset",
            },
        )
        assert created.status_code == 201
        asset_id = created.json()["asset_id"]

        assets = client.get("/assets")
        assert assets.status_code == 200
        asset = next(item for item in assets.json() if item["id"] == asset_id)
        assert asset["name"] == "贵州茅台"
        assert asset["include_in_portfolio"] is False
        assert asset["group_id"] is None
        assert asset["latest_price"] == 1700

        snapshot = client.get("/portfolio/snapshot")
        assert snapshot.status_code == 200
        body = snapshot.json()
        assert body["total_value"] == 0
        assert body["total_holdings_value"] == 1700
        assert body["pending_classification_count"] == 1
        assert body["pending_classification_value"] == 1700
        assert body["items"] == []
        assert len(body["all_items"]) == 1

        structure = client.get("/portfolio/structure")
        assert structure.status_code == 200
        stock_group_id = next(bucket for bucket in structure.json() if bucket["name"] == "股票")["groups"][0]["id"]
        classified = client.put(
            f"/assets/{asset_id}",
            json={
                "group_id": stock_group_id,
                "name": asset["name"],
                "platform": asset["platform"],
                "type": asset["type"],
                "code": asset["code"],
                "exchange": asset["exchange"],
                "target_weight": asset["target_weight"],
                "is_active": asset["is_active"],
                "include_in_portfolio": True,
            },
        )
        assert classified.status_code == 200

        snapshot = client.get("/portfolio/snapshot")
        assert snapshot.status_code == 200
        body = snapshot.json()
        assert body["total_value"] == 1700
        assert body["total_holdings_value"] == 1700
        assert body["pending_classification_count"] == 0
        assert len(body["items"]) == 1

    cleanup_test_db()


def test_asset_delete_allows_unused_assets_and_price_cache_but_blocks_transactions():
    reset_test_db()

    with TestClient(app) as client:
        structure = client.get("/portfolio/structure")
        assert structure.status_code == 200
        stock_group_id = next(bucket for bucket in structure.json() if bucket["name"] == "股票")["groups"][0]["id"]

        unused = client.post(
            "/assets",
            json=asset_payload(group_id=stock_group_id, name="误建标的", code="000001", exchange="SZ"),
        )
        assert unused.status_code == 201
        unused_id = unused.json()["id"]

        deleted = client.delete(f"/assets/{unused_id}")
        assert deleted.status_code == 204
        assert all(item["id"] != unused_id for item in client.get("/assets").json())

        priced = client.post(
            "/assets",
            json=asset_payload(group_id=None, name="仅有价格的误建标的", code="000002", exchange="SZ", include_in_portfolio=False),
        )
        assert priced.status_code == 201
        priced_id = priced.json()["id"]
        assert client.put(f"/prices/{priced_id}", json={"price": 12.3, "date": TODAY}).status_code == 200

        priced_assets = client.get("/assets")
        assert priced_assets.status_code == 200
        priced_asset = next(item for item in priced_assets.json() if item["id"] == priced_id)
        assert priced_asset["price_count"] == 1

        priced_delete = client.delete(f"/assets/{priced_id}")
        assert priced_delete.status_code == 204
        assert all(item["id"] != priced_id for item in client.get("/assets").json())

        traded = client.post(
            "/assets",
            json=asset_payload(group_id=stock_group_id, name="已有交易标的", code="000003", exchange="SZ"),
        )
        assert traded.status_code == 201
        traded_id = traded.json()["id"]
        assert client.post(
            "/transactions",
            json={
                "date": TODAY,
                "asset_id": traded_id,
                "type": "buy",
                "qty": 10,
                "price": 3,
                "fee": 0,
                "note": "cannot delete",
            },
        ).status_code == 201

        blocked = client.delete(f"/assets/{traded_id}")
        assert blocked.status_code == 409
        assert "1 笔交易" in blocked.json()["detail"]
        assert any(item["id"] == traded_id for item in client.get("/assets").json())

    cleanup_test_db()
