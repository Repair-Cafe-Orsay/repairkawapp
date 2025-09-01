"""add app_setting table (maintenance mode)

Revision ID: 20250831_19
Revises: 20250831_18
Create Date: 2025-09-01
"""

from alembic import op
import sqlalchemy as sa

revision = "20250831_19"
down_revision = "20250831_18"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    # Crée la table si absente (idempotent pour environnements divergents)
    res = conn.execute(sa.text("SHOW TABLES LIKE 'app_setting'"))
    if not res.fetchone():
        op.create_table(
            "app_setting",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "maintenance_mode", sa.Boolean(), nullable=False, server_default=sa.text("0")
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
        )
        conn.execute(sa.text("INSERT INTO app_setting (id, maintenance_mode) VALUES (1, 0)"))
    else:
        # S'assure que les colonnes existent (en cas de table partielle)
        cols = {r[0] for r in conn.execute(sa.text("SHOW COLUMNS FROM app_setting"))}
        if "maintenance_mode" not in cols:
            op.add_column(
                "app_setting",
                sa.Column(
                    "maintenance_mode", sa.Boolean(), nullable=False, server_default=sa.text("0")
                ),
            )
        if "updated_at" not in cols:
            op.add_column(
                "app_setting",
                sa.Column(
                    "updated_at",
                    sa.DateTime(),
                    nullable=False,
                    server_default=sa.text("CURRENT_TIMESTAMP"),
                ),
            )
        # S'assure qu'une ligne existe
        row = conn.execute(sa.text("SELECT id FROM app_setting WHERE id=1")).fetchone()
        if not row:
            conn.execute(sa.text("INSERT INTO app_setting (id, maintenance_mode) VALUES (1, 0)"))


def downgrade():
    op.drop_table("app_setting")
