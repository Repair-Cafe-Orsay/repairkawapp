"""Add public_trombi column to user (legacy visibility flag)

Revision ID: 20250831_17
Revises: 20250831_16_add_last_connection
Create Date: 2025-08-31
"""

from alembic import op
import sqlalchemy as sa

revision = "20250831_17"
down_revision = "20250831_16_add_last_connection"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    existing = {row[0] for row in conn.execute(sa.text("SHOW COLUMNS FROM `user`"))}
    if "public_trombi" not in existing:
        op.add_column(
            "user",
            sa.Column("public_trombi", sa.Boolean(), nullable=False, server_default="1"),
        )
        # Normalisation: forcer 1 sur lignes existantes si besoin
        conn.execute(sa.text("UPDATE `user` SET public_trombi=1 WHERE public_trombi IS NULL"))
    else:
        # S'assure que NOT NULL + default=1
        col_info = conn.execute(sa.text("SHOW COLUMNS FROM `user` LIKE 'public_trombi'"))
        row = col_info.fetchone()
        if row is not None:
            # row: Field, Type, Null, Key, Default, Extra
            if row[2] == "YES":
                conn.execute(
                    sa.text(
                        "ALTER TABLE `user` MODIFY `public_trombi` TINYINT(1) NOT NULL DEFAULT 1"
                    )
                )
            if row[4] is None:
                conn.execute(sa.text("ALTER TABLE `user` ALTER `public_trombi` SET DEFAULT 1"))


def downgrade():
    conn = op.get_bind()
    res = conn.execute(sa.text("SHOW COLUMNS FROM `user` LIKE 'public_trombi'"))
    if res.fetchone():
        op.drop_column("user", "public_trombi")
