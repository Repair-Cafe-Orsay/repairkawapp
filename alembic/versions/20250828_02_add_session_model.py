"""Add session model and relations

Revision ID: 20250828_02
Revises: 20250828_01
Create Date: 2025-08-28
"""

from alembic import op
import sqlalchemy as sa

revision = "20250828_02"
down_revision = "20250828_01"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "session",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("location", sa.String(length=100)),
        sa.Column(
            "opened_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("owner_id", sa.Integer, sa.ForeignKey("user.id"), nullable=False),
        sa.Column("comment", sa.Text),
    )
    op.create_table(
        "association_session_user",
        sa.Column("session_id", sa.Integer, sa.ForeignKey("session.id")),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("user.id")),
    )
    with op.batch_alter_table("repair") as batch_op:
        batch_op.add_column(
            sa.Column("session_id", sa.Integer, sa.ForeignKey("session.id"), nullable=True)
        )


def downgrade():
    with op.batch_alter_table("repair") as batch_op:
        batch_op.drop_column("session_id")
    op.drop_table("association_session_user")
    op.drop_table("session")
