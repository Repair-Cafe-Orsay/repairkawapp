"""Decrement existing last_membership values by 1 (semantic shift)

Revision ID: 20250901_24
Revises: 20250901_23
Create Date: 2025-09-01
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20250901_24"
down_revision = "20250901_23"
branch_labels = None
depends_on = None


def upgrade():
    # Decrement last_membership by 1 where not null
    conn = op.get_bind()
    dialect = conn.dialect.name
    # "user" est un mot réservé MySQL -> utiliser backticks
    tbl = "`user`" if dialect == "mysql" else '"user"'
    conn.execute(
        sa.text(
            f"""
        UPDATE {tbl}
        SET last_membership = last_membership - 1
        WHERE last_membership IS NOT NULL
    """
        )
    )


def downgrade():
    # Revert: increment back by 1
    conn = op.get_bind()
    dialect = conn.dialect.name
    tbl = "`user`" if dialect == "mysql" else '"user"'
    conn.execute(
        sa.text(
            f"""
        UPDATE {tbl}
        SET last_membership = last_membership + 1
        WHERE last_membership IS NOT NULL
    """
        )
    )
