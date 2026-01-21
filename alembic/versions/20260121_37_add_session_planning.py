"""Add planning fields to sessions.

Revision ID: 20260121_37
Revises: 20260121_36
Create Date: 2026-01-21
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260121_37"
down_revision = "20260121_36"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("session", sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "session",
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
    )
    # Backfill status from closed_at
    op.execute("UPDATE session SET status='closed' WHERE closed_at IS NOT NULL")
    op.execute("UPDATE session SET status='open' WHERE closed_at IS NULL")
    op.create_index(
        "idx_session_cafe_scheduled_location",
        "session",
        ["repaircafe_id", "scheduled_at", "location_id"],
    )


def downgrade():
    op.drop_index("idx_session_cafe_scheduled_location", table_name="session")
    op.drop_column("session", "status")
    op.drop_column("session", "scheduled_at")
