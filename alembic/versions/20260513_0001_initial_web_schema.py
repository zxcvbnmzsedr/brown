"""initial web schema

Revision ID: 20260513_0001
Revises:
Create Date: 2026-05-13
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260513_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"])
    op.create_index(op.f("ix_users_id"), "users", ["id"])

    op.create_table(
        "trading_platforms",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("account_type", sa.String(length=80), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_trading_platforms_id"), "trading_platforms", ["id"])
    op.create_index(op.f("ix_trading_platforms_name"), "trading_platforms", ["name"])
    op.create_index(op.f("ix_trading_platforms_type"), "trading_platforms", ["type"])

    op.create_table(
        "instruments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=True),
        sa.Column("exchange", sa.String(length=32), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_fetched_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", "exchange", name="uq_instruments_code_exchange"),
    )
    op.create_index(op.f("ix_instruments_code"), "instruments", ["code"])
    op.create_index(op.f("ix_instruments_exchange"), "instruments", ["exchange"])
    op.create_index(op.f("ix_instruments_id"), "instruments", ["id"])
    op.create_index(op.f("ix_instruments_name"), "instruments", ["name"])
    op.create_index(op.f("ix_instruments_type"), "instruments", ["type"])

    op.create_table(
        "portfolios",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("base_currency", sa.String(length=8), nullable=False),
        sa.Column("strategy_type", sa.String(length=64), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_portfolios_id"), "portfolios", ["id"])
    op.create_index(op.f("ix_portfolios_user_id"), "portfolios", ["user_id"])

    op.create_table(
        "instrument_prices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("instrument_id", "date", name="uq_instrument_prices_instrument_date"),
    )
    op.create_index(op.f("ix_instrument_prices_date"), "instrument_prices", ["date"])
    op.create_index(op.f("ix_instrument_prices_id"), "instrument_prices", ["id"])
    op.create_index(op.f("ix_instrument_prices_instrument_id"), "instrument_prices", ["instrument_id"])

    op.create_table(
        "portfolio_buckets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("portfolio_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("target_weight", sa.Float(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_portfolio_buckets_id"), "portfolio_buckets", ["id"])
    op.create_index(op.f("ix_portfolio_buckets_portfolio_id"), "portfolio_buckets", ["portfolio_id"])
    op.create_index(op.f("ix_portfolio_buckets_user_id"), "portfolio_buckets", ["user_id"])

    op.create_table(
        "portfolio_groups",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("portfolio_id", sa.Integer(), nullable=False),
        sa.Column("bucket_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("target_weight", sa.Float(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["bucket_id"], ["portfolio_buckets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_portfolio_groups_bucket_id"), "portfolio_groups", ["bucket_id"])
    op.create_index(op.f("ix_portfolio_groups_id"), "portfolio_groups", ["id"])
    op.create_index(op.f("ix_portfolio_groups_portfolio_id"), "portfolio_groups", ["portfolio_id"])
    op.create_index(op.f("ix_portfolio_groups_user_id"), "portfolio_groups", ["user_id"])

    op.create_table(
        "investment_accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("portfolio_id", sa.Integer(), nullable=False),
        sa.Column("trading_platform_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["trading_platform_id"], ["trading_platforms.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_investment_accounts_id"), "investment_accounts", ["id"])
    op.create_index(op.f("ix_investment_accounts_portfolio_id"), "investment_accounts", ["portfolio_id"])
    op.create_index(op.f("ix_investment_accounts_trading_platform_id"), "investment_accounts", ["trading_platform_id"])
    op.create_index(op.f("ix_investment_accounts_user_id"), "investment_accounts", ["user_id"])

    op.create_table(
        "cash_accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("portfolio_id", sa.Integer(), nullable=False),
        sa.Column("trading_platform_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("balance", sa.Float(), nullable=False),
        sa.Column("balance_date", sa.Date(), nullable=False),
        sa.Column("include_in_rebalance", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["trading_platform_id"], ["trading_platforms.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_cash_accounts_id"), "cash_accounts", ["id"])
    op.create_index(op.f("ix_cash_accounts_portfolio_id"), "cash_accounts", ["portfolio_id"])
    op.create_index(op.f("ix_cash_accounts_trading_platform_id"), "cash_accounts", ["trading_platform_id"])
    op.create_index(op.f("ix_cash_accounts_user_id"), "cash_accounts", ["user_id"])

    op.create_table(
        "user_assets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("portfolio_id", sa.Integer(), nullable=False),
        sa.Column("portfolio_group_id", sa.Integer(), nullable=True),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=True),
        sa.Column("display_name", sa.String(length=120), nullable=True),
        sa.Column("target_weight", sa.Float(), nullable=False),
        sa.Column("include_in_rebalance", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["investment_accounts.id"]),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"]),
        sa.ForeignKeyConstraint(["portfolio_group_id"], ["portfolio_groups.id"]),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "portfolio_id", "instrument_id", name="uq_user_assets_portfolio_instrument"),
    )
    op.create_index(op.f("ix_user_assets_account_id"), "user_assets", ["account_id"])
    op.create_index(op.f("ix_user_assets_id"), "user_assets", ["id"])
    op.create_index(op.f("ix_user_assets_instrument_id"), "user_assets", ["instrument_id"])
    op.create_index(op.f("ix_user_assets_portfolio_group_id"), "user_assets", ["portfolio_group_id"])
    op.create_index(op.f("ix_user_assets_portfolio_id"), "user_assets", ["portfolio_id"])
    op.create_index(op.f("ix_user_assets_user_id"), "user_assets", ["user_id"])

    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("portfolio_id", sa.Integer(), nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=True),
        sa.Column("cash_account_id", sa.Integer(), nullable=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("qty", sa.Float(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("fee", sa.Float(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["investment_accounts.id"]),
        sa.ForeignKeyConstraint(["cash_account_id"], ["cash_accounts.id"]),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"]),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_transactions_account_id"), "transactions", ["account_id"])
    op.create_index(op.f("ix_transactions_cash_account_id"), "transactions", ["cash_account_id"])
    op.create_index(op.f("ix_transactions_date"), "transactions", ["date"])
    op.create_index(op.f("ix_transactions_id"), "transactions", ["id"])
    op.create_index(op.f("ix_transactions_instrument_id"), "transactions", ["instrument_id"])
    op.create_index(op.f("ix_transactions_portfolio_id"), "transactions", ["portfolio_id"])
    op.create_index(op.f("ix_transactions_type"), "transactions", ["type"])
    op.create_index(op.f("ix_transactions_user_id"), "transactions", ["user_id"])

    op.create_table(
        "snapshot_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("portfolio_id", sa.Integer(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("total_value", sa.Float(), nullable=False),
        sa.Column("bucket_data", sa.Text(), nullable=False),
        sa.Column("item_data", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_snapshot_history_id"), "snapshot_history", ["id"])
    op.create_index(op.f("ix_snapshot_history_portfolio_id"), "snapshot_history", ["portfolio_id"])
    op.create_index(op.f("ix_snapshot_history_recorded_at"), "snapshot_history", ["recorded_at"])
    op.create_index(op.f("ix_snapshot_history_user_id"), "snapshot_history", ["user_id"])


def downgrade() -> None:
    op.drop_table("snapshot_history")
    op.drop_table("transactions")
    op.drop_table("user_assets")
    op.drop_table("cash_accounts")
    op.drop_table("investment_accounts")
    op.drop_table("portfolio_groups")
    op.drop_table("portfolio_buckets")
    op.drop_table("instrument_prices")
    op.drop_table("portfolios")
    op.drop_table("instruments")
    op.drop_table("trading_platforms")
    op.drop_table("users")
