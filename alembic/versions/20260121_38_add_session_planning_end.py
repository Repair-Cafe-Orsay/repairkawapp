"""Add planned end time to sessions.

Revision ID: 20260121_38
Revises: 20260121_37
Create Date: 2026-01-21
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260121_38"
down_revision = "20260121_37"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "session", sa.Column("scheduled_end_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade():
    op.drop_column("session", "scheduled_end_at")
