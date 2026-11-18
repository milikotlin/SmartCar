"""inspection_records: results of annual inspections (history input of Model 2)

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-19

"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "inspection_records",
        sa.Column("inspection_id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("license_plate", sa.String(15), sa.ForeignKey("vehicles.license_plate", ondelete="CASCADE"), nullable=False),
        sa.Column("inspection_date", sa.Date, nullable=False),
        sa.Column("odometer_km", sa.Integer),
        sa.Column("brakes_defect", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("electrical_defect", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("engine_defect", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("other_defect", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.Text),
        sa.UniqueConstraint("license_plate", "inspection_date", name="uq_inspection_plate_date"),
    )
    op.create_index("ix_inspection_records_plate", "inspection_records", ["license_plate"])
    op.create_index("ix_maintenance_records_plate", "maintenance_records", ["license_plate"])


def downgrade() -> None:
    op.drop_index("ix_maintenance_records_plate", table_name="maintenance_records")
    op.drop_index("ix_inspection_records_plate", table_name="inspection_records")
    op.drop_table("inspection_records")
