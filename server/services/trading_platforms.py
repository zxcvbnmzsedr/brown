from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from server.models import TradingPlatform


@dataclass(frozen=True)
class TradingPlatformSeed:
    name: str
    type: str
    account_type: str | None
    display_order: int


DEFAULT_TRADING_PLATFORMS = [
    TradingPlatformSeed("招商银行", "broker", "证券账户", 10),
    TradingPlatformSeed("华泰证券", "broker", "证券账户", 20),
    TradingPlatformSeed("中信证券", "broker", "证券账户", 30),
    TradingPlatformSeed("招商证券", "broker", "证券账户", 40),
    TradingPlatformSeed("国泰海通证券", "broker", "证券账户", 50),
    TradingPlatformSeed("广发证券", "broker", "证券账户", 60),
    TradingPlatformSeed("银河证券", "broker", "证券账户", 70),
    TradingPlatformSeed("国信证券", "broker", "证券账户", 80),
    TradingPlatformSeed("申万宏源证券", "broker", "证券账户", 90),
    TradingPlatformSeed("东方财富证券", "broker", "证券账户", 100),
    TradingPlatformSeed("平安证券", "broker", "证券账户", 110),
    TradingPlatformSeed("兴业证券", "broker", "证券账户", 120),
    TradingPlatformSeed("方正证券", "broker", "证券账户", 130),
    TradingPlatformSeed("长桥证券", "broker", "港美股证券账户", 140),
    TradingPlatformSeed("富途牛牛", "broker", "港美股证券账户", 150),
    TradingPlatformSeed("老虎证券", "broker", "港美股证券账户", 160),
    TradingPlatformSeed("支付宝蚂蚁基金", "fund_platform", "基金账户", 210),
    TradingPlatformSeed("京东肯特瑞基金", "fund_platform", "基金账户", 220),
    TradingPlatformSeed("百度度小满基金", "fund_platform", "基金账户", 230),
    TradingPlatformSeed("腾讯腾安基金", "fund_platform", "基金账户", 240),
    TradingPlatformSeed("天天基金", "fund_platform", "基金账户", 250),
    TradingPlatformSeed("蛋卷基金", "fund_platform", "基金账户", 260),
    TradingPlatformSeed("工商银行", "bank", "银行卡", 310),
    TradingPlatformSeed("建设银行", "bank", "银行卡", 320),
    TradingPlatformSeed("中国银行", "bank", "银行卡", 330),
    TradingPlatformSeed("农业银行", "bank", "银行卡", 340),
    TradingPlatformSeed("交通银行", "bank", "银行卡", 350),
    TradingPlatformSeed("邮储银行", "bank", "银行卡", 360),
    TradingPlatformSeed("支付宝余额宝", "payment", "现金账户", 410),
    TradingPlatformSeed("微信零钱通", "payment", "现金账户", 420),
]


def seed_default_trading_platforms(db: Session) -> dict[str, int]:
    inserted = 0
    updated = 0
    for seed in DEFAULT_TRADING_PLATFORMS:
        platform = db.scalars(
            select(TradingPlatform)
            .where(TradingPlatform.name == seed.name)
            .limit(1)
        ).first()
        if platform is None:
            db.add(
                TradingPlatform(
                    name=seed.name,
                    type=seed.type,
                    account_type=seed.account_type,
                    display_order=seed.display_order,
                    is_active=True,
                )
            )
            inserted += 1
        else:
            platform.type = seed.type
            platform.account_type = seed.account_type
            platform.display_order = seed.display_order
            platform.is_active = True
            updated += 1
    db.flush()
    return {
        "total_count": len(DEFAULT_TRADING_PLATFORMS),
        "inserted_count": inserted,
        "updated_count": updated,
    }
