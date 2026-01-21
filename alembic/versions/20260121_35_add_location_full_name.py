"""Add full name for locations.

Revision ID: 20260121_35
Revises: 20260121_34
Create Date: 2026-01-21
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260121_35"
down_revision = "20260121_34"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("location", sa.Column("full_name", sa.String(200), nullable=True))
    # Par défaut, répliquer le nom court dans le nom complet
    op.execute("UPDATE location SET full_name = name WHERE full_name IS NULL")


def downgrade():
    op.drop_column("location", "full_name")
