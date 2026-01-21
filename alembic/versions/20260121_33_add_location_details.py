"""Add address and recurrence to locations.

Revision ID: 20260121_33
Revises: 20260120_32
Create Date: 2026-01-21
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260121_33"
down_revision = "20260120_32"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("location", sa.Column("address", sa.String(200), nullable=True))
    op.add_column(
        "location",
        sa.Column("is_recurring", sa.Boolean(), nullable=False, server_default="1"),
    )

    # Par défaut, les lieux existants sont récurrents
    op.execute("UPDATE location SET is_recurring=1 WHERE is_recurring IS NULL")


def downgrade():
    op.drop_column("location", "is_recurring")
    op.drop_column("location", "address")
