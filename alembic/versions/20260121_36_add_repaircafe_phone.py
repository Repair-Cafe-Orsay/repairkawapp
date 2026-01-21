"""Add RepairCafe phone contact.

Revision ID: 20260121_36
Revises: 20260121_35
Create Date: 2026-01-21
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260121_36"
down_revision = "20260121_35"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("repaircafe", sa.Column("phone", sa.String(30), nullable=True))


def downgrade():
    op.drop_column("repaircafe", "phone")
