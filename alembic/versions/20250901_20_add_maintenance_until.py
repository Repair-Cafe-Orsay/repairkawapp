"""add maintenance_until to app_setting

Revision ID: 20250901_20
Revises: 20250831_19
Create Date: 2025-09-01
"""

from alembic import op
import sqlalchemy as sa

revision = "20250901_20"
down_revision = "20250831_19"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    res = conn.execute(sa.text("SHOW COLUMNS FROM app_setting LIKE 'maintenance_until'"))
    if not res.fetchone():
        op.add_column("app_setting", sa.Column("maintenance_until", sa.DateTime(), nullable=True))


def downgrade():
    conn = op.get_bind()
    res = conn.execute(sa.text("SHOW COLUMNS FROM app_setting LIKE 'maintenance_until'"))
    if res.fetchone():
        op.drop_column("app_setting", "maintenance_until")
