"""Add per-cafe user photo

Revision ID: 20260120_27
Revises: 20260119_26
Create Date: 2026-01-20
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260120_27"
down_revision = "20260119_26"
branch_labels = None
depends_on = None


def _quote_user_table(dialect: str) -> str:
    return "`user`" if dialect == "mysql" else '"user"'


def upgrade():
    op.add_column(
        "association_user_repaircafe",
        sa.Column("photo_filename", sa.String(200), nullable=True),
    )

    conn = op.get_bind()
    dialect = conn.dialect.name
    user_tbl = _quote_user_table(dialect)

    if dialect == "mysql":
        conn.execute(
            sa.text(
                f"""
                UPDATE association_user_repaircafe aur
                JOIN {user_tbl} u ON u.id = aur.user_id
                SET aur.photo_filename = u.photo_filename
                WHERE u.photo_filename IS NOT NULL
                """
            )
        )
    else:
        conn.execute(
            sa.text(
                f"""
                UPDATE association_user_repaircafe
                SET photo_filename = (
                    SELECT photo_filename FROM {user_tbl} u
                    WHERE u.id = association_user_repaircafe.user_id
                )
                WHERE (
                    SELECT photo_filename FROM {user_tbl} u
                    WHERE u.id = association_user_repaircafe.user_id
                ) IS NOT NULL
                """
            )
        )


def downgrade():
    op.drop_column("association_user_repaircafe", "photo_filename")
