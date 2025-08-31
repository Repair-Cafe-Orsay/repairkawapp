"""add unique constraint on object_type (name, category_id)

Revision ID: 20250831_11
Revises: 20250830_10
Create Date: 2025-08-31
"""

from alembic import op

revision = "20250831_11"
down_revision = "20250830_10"
branch_labels = None
depends_on = None


def upgrade():
    # Contrainte déjà créée dans 20250830_10 si base neuve. Ici on vérifie existence.
    # Alembic ne fournit pas d'API portable pour if-not-exists; on tente et ignore si échec.
    try:
        op.create_unique_constraint(
            "uix_object_type_name_category", "object_type", ["name", "category_id"]
        )
    except Exception:
        pass


def downgrade():
    try:
        op.drop_constraint("uix_object_type_name_category", "object_type", type_="unique")
    except Exception:
        pass
