"""Add rm_uploaded timestamp on repair

Revision ID: 20251202_25
Revises: 20250901_24
Create Date: 2025-12-02
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20251202_25"
down_revision = "20250901_24"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("repair", sa.Column("rm_uploaded", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("repair", "rm_uploaded")
