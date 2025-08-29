"""Add user profile fields (board_title, biography, photo_filename) and BoardRoleLog

Revision ID: 20250828_05
Revises: 20250828_04
Create Date: 2025-08-28
"""

from alembic import op
import sqlalchemy as sa

revision = "20250828_05"
down_revision = "20250828_04"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("user") as batch_op:
        batch_op.add_column(sa.Column("board_title", sa.String(length=30)))
        batch_op.add_column(sa.Column("biography", sa.Text()))
        batch_op.add_column(sa.Column("photo_filename", sa.String(length=200)))
    op.create_table(
        "boardrolelog",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "date",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("admin_id", sa.Integer, sa.ForeignKey("user.id"), nullable=False),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("user.id"), nullable=False),
        sa.Column("old_role", sa.String(length=30)),
        sa.Column("new_role", sa.String(length=30)),
    )


def downgrade():
    op.drop_table("boardrolelog")
    with op.batch_alter_table("user") as batch_op:
        batch_op.drop_column("photo_filename")
        batch_op.drop_column("biography")
        batch_op.drop_column("board_title")
