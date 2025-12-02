"""Store RepairMonitor identifier instead of timestamp

Revision ID: 20251202_26
Revises: 20251202_25
Create Date: 2025-12-02
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20251202_26"
down_revision = "20251202_25"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("repair") as batch_op:
        batch_op.alter_column(
            "rm_uploaded",
            existing_type=sa.DateTime(timezone=True),
            type_=sa.String(length=32),
            existing_nullable=True,
        )


def downgrade():
    with op.batch_alter_table("repair") as batch_op:
        batch_op.alter_column(
            "rm_uploaded",
            existing_type=sa.String(length=32),
            type_=sa.DateTime(timezone=True),
            existing_nullable=True,
        )
