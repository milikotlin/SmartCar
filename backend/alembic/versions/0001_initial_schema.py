"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-08-30

"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vehicles",
        sa.Column("license_plate", sa.String(15), primary_key=True),
        sa.Column("make", sa.String(50), nullable=False),
        sa.Column("model", sa.String(50), nullable=False),
        sa.Column("manufacture_year", sa.Integer, nullable=False),
        sa.Column("current_mileage", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.current_timestamp()),
    )

    op.create_table(
        "maintenance_records",
        sa.Column("record_id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "license_plate",
            sa.String(15),
            sa.ForeignKey("vehicles.license_plate", ondelete="CASCADE"),
        ),
        sa.Column("service_date", sa.Date, nullable=False),
        sa.Column("mileage_at_service", sa.Integer, nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("maintenance_category", sa.String(50)),
        sa.Column("total_cost", sa.Numeric(10, 2), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("maintenance_records")
    op.drop_table("vehicles")
