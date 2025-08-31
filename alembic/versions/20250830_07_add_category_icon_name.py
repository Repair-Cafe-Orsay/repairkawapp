"""add icon_name column to category

Revision ID: 20250830_07
Revises: 20250828_06
Create Date: 2025-08-30
"""

from alembic import op
import sqlalchemy as sa

revision = "20250830_07"
down_revision = "20250828_06"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("category") as batch_op:
        batch_op.add_column(sa.Column("icon_name", sa.String(length=50), nullable=True))


def downgrade():
    with op.batch_alter_table("category") as batch_op:
        batch_op.drop_column("icon_name")
