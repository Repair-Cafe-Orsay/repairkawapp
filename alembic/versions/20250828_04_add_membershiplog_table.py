"""Add MembershipLog table

Revision ID: 20250828_04
Revises: 20250828_03
Create Date: 2025-08-28
"""

from alembic import op
import sqlalchemy as sa

revision = "20250828_04"
down_revision = "20250828_03"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "membershiplog",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "date",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("admin_id", sa.Integer, sa.ForeignKey("user.id"), nullable=False),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("user.id"), nullable=False),
        sa.Column("old_value", sa.Integer),
        sa.Column("new_value", sa.Integer),
        sa.Column("note", sa.String(length=200), server_default=""),
    )


def downgrade():
    op.drop_table("membershiplog")
