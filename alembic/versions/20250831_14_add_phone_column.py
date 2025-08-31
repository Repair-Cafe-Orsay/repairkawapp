"""add phone column to user (if missing)

Revision ID: 20250831_14
Revises: 20250831_13
Create Date: 2025-08-31
"""

from alembic import op
import sqlalchemy as sa

revision = "20250831_14"
down_revision = "20250831_13"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    res = conn.execute(sa.text("SHOW COLUMNS FROM `user`"))
    existing = {row[0] for row in res}
    if "phone" not in existing:
        op.add_column("user", sa.Column("phone", sa.String(length=30), nullable=True))


def downgrade():
    conn = op.get_bind()
    res = conn.execute(sa.text("SHOW COLUMNS FROM `user` LIKE 'phone'"))
    if res.fetchone():
        op.drop_column("user", "phone")


"""add phone column to user (if missing)

Revision ID: 20250831_14
Revises: 20250831_13
Create Date: 2025-08-31
"""
from alembic import op
import sqlalchemy as sa

revision = "20250831_14"
down_revision = "20250831_13"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    res = conn.execute(sa.text("SHOW COLUMNS FROM `user`"))
    existing = {row[0] for row in res}
    if "phone" not in existing:
        op.add_column("user", sa.Column("phone", sa.String(length=30), nullable=True))


def downgrade():
    conn = op.get_bind()
    res = conn.execute(sa.text("SHOW COLUMNS FROM `user` LIKE 'phone'"))
    if res.fetchone():
        op.drop_column("user", "phone")
