"""Add cafe file storage

Revision ID: 20260120_30
Revises: 20260120_29
Create Date: 2026-01-20
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260120_30"
down_revision = "20260120_29"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "cafe_file",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("repaircafe_id", sa.Integer, sa.ForeignKey("repaircafe.id"), nullable=False),
        sa.Column("sender_id", sa.Integer, sa.ForeignKey("user.id"), nullable=False),
        sa.Column("file_name", sa.String(256), nullable=False),
        sa.Column("file_path", sa.String(256), nullable=False),
        sa.Column("creation", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_cafe_file_sender", "cafe_file", ["sender_id"])
    op.create_index("idx_cafe_file_cafe", "cafe_file", ["repaircafe_id"])


def downgrade():
    op.drop_index("idx_cafe_file_cafe", table_name="cafe_file")
    op.drop_index("idx_cafe_file_sender", table_name="cafe_file")
    op.drop_table("cafe_file")
