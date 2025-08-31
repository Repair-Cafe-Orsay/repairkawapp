"""add founder flag

Revision ID: 20250831_15_add_founder_flag
Revises: 20250831_14_add_phone_column
Create Date: 2025-08-31
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20250831_15_add_founder_flag"
# Corrige la chaîne: la révision précédente a l'ID "20250831_14" (sans suffixe)
down_revision = "20250831_14"
branch_labels = None
depends_on = None


def upgrade():
    # Idempotence: si la colonne existe déjà (ex: ajout manuel), ne rien faire.
    conn = op.get_bind()
    res = conn.execute(sa.text("SHOW COLUMNS FROM `user` LIKE 'founder'"))
    if res.fetchone():
        return
    with op.batch_alter_table("user") as batch_op:
        batch_op.add_column(sa.Column("founder", sa.Boolean(), server_default="0", nullable=False))


def downgrade():
    with op.batch_alter_table("user") as batch_op:
        batch_op.drop_column("founder")
