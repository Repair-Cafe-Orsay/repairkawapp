"""add new categories O/P/Q

Revision ID: 20250830_09
Revises: 20250830_08
Create Date: 2025-08-30
"""

from alembic import op
import sqlalchemy as sa

revision = "20250830_09"
down_revision = "20250830_08"
branch_labels = None
depends_on = None

NEW_CATEGORIES = [
    {"name": "O - Éclairage", "rm_icon_id": 1685, "icon_name": "lightbulb"},
    {"name": "P - Chauffage/Climatisation", "rm_icon_id": 1685, "icon_name": "thermometer-half"},
    {"name": "Q - Sécurité/Domotique", "rm_icon_id": 1685, "icon_name": "shield-lock"},
]


def upgrade():
    conn = op.get_bind()
    for cat in NEW_CATEGORIES:
        exists = conn.execute(
            sa.text("SELECT 1 FROM category WHERE name=:n"), {"n": cat["name"]}
        ).first()
        if not exists:
            conn.execute(
                sa.text(
                    "INSERT INTO category (name, rm_icon_id, icon_name) VALUES (:name, :rm, :icon)"
                ),
                {"name": cat["name"], "rm": cat["rm_icon_id"], "icon": cat["icon_name"]},
            )


def downgrade():
    conn = op.get_bind()
    for cat in NEW_CATEGORIES:
        conn.execute(sa.text("DELETE FROM category WHERE name=:n"), {"n": cat["name"]})
