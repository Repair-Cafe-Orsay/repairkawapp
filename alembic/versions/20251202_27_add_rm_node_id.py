"""Add RepairMonitor node id storage

Revision ID: 20251202_27
Revises: 20251202_26
Create Date: 2026-01-01
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20251202_27"
down_revision = "20251202_26"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("repair") as batch_op:
        batch_op.add_column(sa.Column("rm_node_id", sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table("repair") as batch_op:
        batch_op.drop_column("rm_node_id")
