"""Add website_url to RepairCafe

Revision ID: 20260120_29
Revises: 20260120_28
Create Date: 2026-01-20
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260120_29"
down_revision = "20260120_28"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("repaircafe", sa.Column("website_url", sa.String(200), nullable=True))

    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE repaircafe
            SET website_url = :url
            WHERE (code = :code OR slug = :slug) AND website_url IS NULL
            """
        ),
        {"url": "https://repaircafe-orsay.org", "code": "rco", "slug": "repaircafe-orsay"},
    )


def downgrade():
    op.drop_column("repaircafe", "website_url")
