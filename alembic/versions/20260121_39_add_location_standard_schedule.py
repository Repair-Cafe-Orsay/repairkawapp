"""Add standard schedule fields for locations.

Revision ID: 20260121_39
Revises: 20260121_38
Create Date: 2026-01-21
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260121_39"
down_revision = "20260121_38"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("location", sa.Column("standard_day", sa.String(50), nullable=True))
    op.add_column("location", sa.Column("standard_open_time", sa.String(10), nullable=True))
    op.add_column("location", sa.Column("standard_close_time", sa.String(10), nullable=True))


def downgrade():
    op.drop_column("location", "standard_close_time")
    op.drop_column("location", "standard_open_time")
    op.drop_column("location", "standard_day")
