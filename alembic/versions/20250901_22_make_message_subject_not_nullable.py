"""make message.subject non nullable

Revision ID: 20250901_22
Revises: 20250901_21
Create Date: 2025-09-01 20:30:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20250901_22"
down_revision = "20250901_21"
branch_labels = None
depends_on = None


def upgrade():
    # Normaliser valeurs NULL éventuelles avant contrainte
    conn = op.get_bind()
    conn.execute(sa.text("UPDATE message SET subject='(Sans sujet)' WHERE subject IS NULL"))
    # Rendre non nullable
    op.alter_column("message", "subject", existing_type=sa.String(length=120), nullable=False)


def downgrade():
    # Autoriser à nouveau NULL
    op.alter_column("message", "subject", existing_type=sa.String(length=120), nullable=True)
