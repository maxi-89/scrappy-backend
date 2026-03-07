"""add offers, pricing and orders tables

Revision ID: a4f1c8e2d905
Revises: 3379ac35ea78
Create Date: 2026-03-07 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a4f1c8e2d905"
down_revision: str | Sequence[str] | None = "3379ac35ea78"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "offers",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("category"),
    )
    op.create_index(op.f("ix_offers_category"), "offers", ["category"], unique=True)
    op.create_index(op.f("ix_offers_is_active"), "offers", ["is_active"], unique=False)

    op.create_table(
        "pricing",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("zone", sa.String(), nullable=False),
        sa.Column("price_usd", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("zone"),
    )
    op.create_index(op.f("ix_pricing_zone"), "pricing", ["zone"], unique=True)

    op.create_table(
        "orders",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("offer_id", sa.String(), nullable=False),
        sa.Column("zone", sa.String(), nullable=False),
        sa.Column("format", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("total_usd", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("stripe_payment_intent_id", sa.String(), nullable=True),
        sa.Column("scraping_job_id", sa.String(), nullable=True),
        sa.Column("result_path", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["offer_id"], ["offers.id"]),
        sa.ForeignKeyConstraint(["scraping_job_id"], ["scraping_jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stripe_payment_intent_id"),
    )
    op.create_index(op.f("ix_orders_user_id"), "orders", ["user_id"], unique=False)
    op.create_index(op.f("ix_orders_status"), "orders", ["status"], unique=False)
    op.create_index(op.f("ix_orders_scraping_job_id"), "orders", ["scraping_job_id"], unique=False)

    # Add FK from scraping_jobs.order_id → orders.id now that orders table exists
    op.create_foreign_key(
        "fk_scraping_jobs_order_id",
        "scraping_jobs",
        "orders",
        ["order_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("fk_scraping_jobs_order_id", "scraping_jobs", type_="foreignkey")

    op.drop_index(op.f("ix_orders_scraping_job_id"), table_name="orders")
    op.drop_index(op.f("ix_orders_status"), table_name="orders")
    op.drop_index(op.f("ix_orders_user_id"), table_name="orders")
    op.drop_table("orders")

    op.drop_index(op.f("ix_pricing_zone"), table_name="pricing")
    op.drop_table("pricing")

    op.drop_index(op.f("ix_offers_is_active"), table_name="offers")
    op.drop_index(op.f("ix_offers_category"), table_name="offers")
    op.drop_table("offers")
