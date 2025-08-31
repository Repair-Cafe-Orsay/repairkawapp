"""insert categories O P Q (placeholder if already present)

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


def upgrade():
    # Insertion sécurisée (ignore si existe) – dépend selon moteur, ici simple tentative.
    conn = op.get_bind()
    existing = {r[0] for r in conn.execute(sa.text("SELECT name FROM category")).fetchall()}
    to_add = [
        (None, "O - Éclairage"),
        (None, "P - Chauffage/Climatisation"),
        (None, "Q - Sécurité/Domotique"),
    ]
    for rm_icon_id, name in to_add:
        if name not in existing:
            conn.execute(
                sa.text(
                    "INSERT INTO category (rm_icon_id, icon_name, name) VALUES (:ri,:ic,:nm)"
                ).bindparams(ri=rm_icon_id, ic=None, nm=name)
            )


def downgrade():
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "DELETE FROM category WHERE name IN ('O - Éclairage','P - Chauffage/Climatisation','Q - Sécurité/Domotique')"
        )
    )
