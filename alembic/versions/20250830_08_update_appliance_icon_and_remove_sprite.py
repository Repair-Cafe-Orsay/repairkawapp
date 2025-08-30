"""update appliance category icon to lightning and remove legacy sprite usage

Revision ID: 20250830_08
Revises: 20250830_07
Create Date: 2025-08-30
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column

revision = "20250830_08"
down_revision = "20250830_07"
branch_labels = None
depends_on = None

category_table = table(
    "category",
    column("id", sa.Integer()),
    column("name", sa.String()),
    column("icon_name", sa.String()),
)


def upgrade():
    conn = op.get_bind()
    # Mettre à jour l'icône de la catégorie électroménager si encore 'plug'
    conn.execute(
        sa.text(
            "UPDATE category SET icon_name='lightning' WHERE name LIKE 'A - Électroménager' AND (icon_name IS NULL OR icon_name='plug')"
        )
    )


def downgrade():
    conn = op.get_bind()
    # Revenir à l'ancienne valeur 'plug' uniquement si actuellement 'lightning'
    conn.execute(
        sa.text(
            "UPDATE category SET icon_name='plug' WHERE name LIKE 'A - Électroménager' AND icon_name='lightning'"
        )
    )
