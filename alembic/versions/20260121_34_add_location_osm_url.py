"""Add OpenStreetMap URL for locations.

Revision ID: 20260121_34
Revises: 20260121_33
Create Date: 2026-01-21
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260121_34"
down_revision = "20260121_33"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("location", sa.Column("osm_url", sa.String(300), nullable=True))


def downgrade():
    op.drop_column("location", "osm_url")
