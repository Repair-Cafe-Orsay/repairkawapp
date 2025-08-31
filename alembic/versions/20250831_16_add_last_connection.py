"""add last_connection field

Revision ID: 20250831_16_add_last_connection
Revises: 20250831_15_add_founder_flag
Create Date: 2025-08-31
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20250831_16_add_last_connection"
down_revision = "20250831_15_add_founder_flag"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("user") as batch_op:
        batch_op.add_column(sa.Column("last_connection", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    with op.batch_alter_table("user") as batch_op:
        batch_op.drop_column("last_connection")
