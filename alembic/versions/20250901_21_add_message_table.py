"""add message table

Revision ID: 20250901_21
Revises: 20250901_20
Create Date: 2025-09-01 18:20:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20250901_21"
down_revision = "20250901_20"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "message",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sender_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("recipient_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("subject", sa.String(length=120)),
        sa.Column("body", sa.String(length=250), nullable=False),
        sa.Column("repair_id", sa.Integer(), sa.ForeignKey("repair.id"), nullable=True),
        sa.Column("note_id", sa.Integer(), sa.ForeignKey("note.id"), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_sender", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("deleted_recipient", sa.Boolean(), server_default=sa.text("0"), nullable=False),
    )
    op.create_index("idx_message_recipient_unread", "message", ["recipient_id", "read_at"])
    op.create_index("ix_message_sender_id", "message", ["sender_id"])
    op.create_index("ix_message_recipient_id", "message", ["recipient_id"])
    op.create_index("ix_message_repair_id", "message", ["repair_id"])
    op.create_index("ix_message_note_id", "message", ["note_id"])
    op.create_index("ix_message_created_at", "message", ["created_at"])


def downgrade():
    op.drop_index("ix_message_created_at", table_name="message")
    op.drop_index("ix_message_note_id", table_name="message")
    op.drop_index("ix_message_repair_id", table_name="message")
    op.drop_index("ix_message_recipient_id", table_name="message")
    op.drop_index("ix_message_sender_id", table_name="message")
    op.drop_index("idx_message_recipient_unread", table_name="message")
    op.drop_table("message")
