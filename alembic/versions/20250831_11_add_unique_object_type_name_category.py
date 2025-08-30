"""add unique constraint on object_type (name, category_id)

Revision ID: 20250831_11
Revises: 20250830_10
Create Date: 2025-08-31
"""

from alembic import op
import sqlalchemy as sa

revision = "20250831_11"
down_revision = "20250830_10"
branch_labels = None
depends_on = None


def upgrade():
    # Ajout contrainte unique si elle n'existe pas déjà
    # Alembic ne fournit pas de if not exists portable -> try/except runtime (DB spécifique) hors scope ici.
    op.create_unique_constraint(
        "uix_object_type_name_category", "object_type", ["name", "category_id"]
    )


def downgrade():
    op.drop_constraint("uix_object_type_name_category", "object_type", type_="unique")
