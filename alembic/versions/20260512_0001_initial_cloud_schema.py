"""initial cloud schema

Revision ID: 20260512_0001
Revises:
Create Date: 2026-05-12
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260512_0001"
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
    op.create_index(op.f("ix_users_id"), "users", ["id"])
    op.create_index(op.f("ix_users_email"), "users", ["email"])

    op.create_table(
        "portfolio_buckets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("target_weight", sa.Float(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_portfolio_buckets_id"), "portfolio_buckets", ["id"])
    op.create_index(op.f("ix_portfolio_buckets_user_id"), "portfolio_buckets", ["user_id"])

    op.create_table(
        "asset_groups",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("bucket_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("target_weight", sa.Float(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["bucket_id"], ["portfolio_buckets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_asset_groups_bucket_id"), "asset_groups", ["bucket_id"])
    op.create_index(op.f("ix_asset_groups_id"), "asset_groups", ["id"])
    op.create_index(op.f("ix_asset_groups_user_id"), "asset_groups", ["user_id"])

    op.create_table(
        "assets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("platform", sa.String(length=120), nullable=True),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=True),
        sa.Column("exchange", sa.String(length=32), nullable=True),
        sa.Column("target_weight", sa.Float(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("include_in_portfolio", sa.Boolean(), nullable=False),
        sa.Column("last_fetched_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["asset_groups.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_assets_group_id"), "assets", ["group_id"])
    op.create_index(op.f("ix_assets_id"), "assets", ["id"])
    op.create_index(op.f("ix_assets_type"), "assets", ["type"])
    op.create_index(op.f("ix_assets_user_id"), "assets", ["user_id"])

    op.create_table(
        "settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "key", name="uq_settings_user_key"),
    )
    op.create_index(op.f("ix_settings_id"), "settings", ["id"])
    op.create_index(op.f("ix_settings_user_id"), "settings", ["user_id"])

    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("qty", sa.Float(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("fee", sa.Float(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_transactions_asset_id"), "transactions", ["asset_id"])
    op.create_index(op.f("ix_transactions_date"), "transactions", ["date"])
    op.create_index(op.f("ix_transactions_id"), "transactions", ["id"])
    op.create_index(op.f("ix_transactions_type"), "transactions", ["type"])
    op.create_index(op.f("ix_transactions_user_id"), "transactions", ["user_id"])

    op.create_table(
        "opening_positions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("qty", sa.Float(), nullable=False),
        sa.Column("cost_price", sa.Float(), nullable=False),
        sa.Column("current_price", sa.Float(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "asset_id", name="uq_opening_positions_user_asset"),
    )
    op.create_index(op.f("ix_opening_positions_asset_id"), "opening_positions", ["asset_id"])
    op.create_index(op.f("ix_opening_positions_date"), "opening_positions", ["date"])
    op.create_index(op.f("ix_opening_positions_id"), "opening_positions", ["id"])
    op.create_index(op.f("ix_opening_positions_user_id"), "opening_positions", ["user_id"])

    op.create_table(
        "price_cache",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_price_cache_asset_id"), "price_cache", ["asset_id"])
    op.create_index(op.f("ix_price_cache_date"), "price_cache", ["date"])
    op.create_index(op.f("ix_price_cache_id"), "price_cache", ["id"])
    op.create_index(op.f("ix_price_cache_user_id"), "price_cache", ["user_id"])

    op.create_table(
        "snapshot_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("total_value", sa.Float(), nullable=False),
        sa.Column("bucket_data", sa.Text(), nullable=False),
        sa.Column("item_data", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_snapshot_history_id"), "snapshot_history", ["id"])
    op.create_index(op.f("ix_snapshot_history_recorded_at"), "snapshot_history", ["recorded_at"])
    op.create_index(op.f("ix_snapshot_history_user_id"), "snapshot_history", ["user_id"])

    op.create_table(
        "rebalance_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("executed_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("config_mode", sa.String(length=32), nullable=False),
        sa.Column("total_value", sa.Float(), nullable=False),
        sa.Column("trigger_reasons", sa.Text(), nullable=False),
        sa.Column("trade_data", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_rebalance_history_executed_at"), "rebalance_history", ["executed_at"])
    op.create_index(op.f("ix_rebalance_history_id"), "rebalance_history", ["id"])
    op.create_index(op.f("ix_rebalance_history_user_id"), "rebalance_history", ["user_id"])


def downgrade() -> None:
    op.drop_table("rebalance_history")
    op.drop_table("snapshot_history")
    op.drop_table("price_cache")
    op.drop_table("opening_positions")
    op.drop_table("transactions")
    op.drop_table("settings")
    op.drop_table("assets")
    op.drop_table("asset_groups")
    op.drop_table("portfolio_buckets")
    op.drop_table("users")
