"""Add Location table and replace session.location with location_id

Revision ID: 20250828_03
Revises: 20250828_02
Create Date: 2025-08-28
"""

from alembic import op
import sqlalchemy as sa

revision = "20250828_03"
down_revision = "20250828_02"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "location",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False, unique=True),
    )
    # Ajout de la colonne location_id
    with op.batch_alter_table("session") as batch_op:
        batch_op.add_column(
            sa.Column("location_id", sa.Integer, sa.ForeignKey("location.id"), nullable=True)
        )
    # Migration best-effort: si l'ancienne colonne 'location' existe, copier les valeurs distinctes
    conn = op.get_bind()
    insp = sa.inspect(conn)
    cols = [c["name"] for c in insp.get_columns("session")]
    if "location" in cols:
        sessions = conn.execute(
            sa.text(
                'SELECT DISTINCT location FROM session WHERE location IS NOT NULL AND location <> ""'
            )
        ).fetchall()
        for (loc,) in sessions:
            conn.execute(sa.text("INSERT IGNORE INTO location(name) VALUES (:n)"), {"n": loc})
        # Associer maintenant (MySQL spécifique: UPDATE join)
        # On récupère mapping fraîchement inséré
        loc_rows = conn.execute(sa.text("SELECT id, name FROM location")).fetchall()
        mapping = {name: _id for _id, name in loc_rows}
        for (loc,) in sessions:
            conn.execute(
                sa.text("UPDATE session SET location_id=:lid WHERE location=:ln"),
                {"lid": mapping.get(loc), "ln": loc},
            )
    # Optionnel: suppression ancienne colonne
    if "location" in cols:
        with op.batch_alter_table("session") as batch_op:
            batch_op.drop_column("location")


def downgrade():
    # Restaurer colonne texte simple
    with op.batch_alter_table("session") as batch_op:
        batch_op.add_column(sa.Column("location", sa.String(length=100)))
    conn = op.get_bind()
    # Re-hydrater location depuis location_id
    conn.execute(
        sa.text("UPDATE session s JOIN location l ON s.location_id=l.id SET s.location=l.name")
    )
    with op.batch_alter_table("session") as batch_op:
        batch_op.drop_column("location_id")
    op.drop_table("location")
