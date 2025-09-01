"""make message body nullable

Revision ID: 20250901_23
Revises: 20250901_22
Create Date: 2025-09-01 22:10:00.000000

"""

from alembic import op
import sqlalchemy as sa

revision = "20250901_23"
down_revision = "20250901_22"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("message") as batch_op:
        batch_op.alter_column("body", existing_type=sa.String(length=250), nullable=True)


def downgrade():
    # ATTENTION: si des lignes ont body NULL, ce downgrade échouera.
    with op.batch_alter_table("message") as batch_op:
        batch_op.alter_column("body", existing_type=sa.String(length=250), nullable=False)
