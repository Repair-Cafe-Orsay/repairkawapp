"""add icon_name to category

Revision ID: 20250830_07
Revises: 20250828_06
Create Date: 2025-08-30
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20250830_07"
down_revision = "20250828_06"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("category", sa.Column("icon_name", sa.String(length=50), nullable=True))


def downgrade():
    op.drop_column("category", "icon_name")
