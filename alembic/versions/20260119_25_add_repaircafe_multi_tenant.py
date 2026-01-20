"""Add RepairCafe multi-tenant scaffolding

Revision ID: 20260119_25
Revises: 20250901_24
Create Date: 2026-01-19
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260119_25"
down_revision = "20250901_24"
branch_labels = None
depends_on = None


def _quote_user_table(dialect: str) -> str:
    return "`user`" if dialect == "mysql" else '"user"'


def upgrade():
    # Create repaircafe table
    op.create_table(
        "repaircafe",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("slug", sa.String(50), nullable=False, unique=True),
        sa.Column("email", sa.String(100), nullable=True),
        sa.Column("logo_filename", sa.String(200), nullable=True),
        sa.Column("timezone", sa.String(50), nullable=True, server_default="Europe/Paris"),
    )

    # Association user <-> repaircafe
    op.create_table(
        "association_user_repaircafe",
        sa.Column("user_id", sa.Integer, sa.ForeignKey("user.id")),
        sa.Column("repaircafe_id", sa.Integer, sa.ForeignKey("repaircafe.id")),
        sa.Column("role", sa.String(30)),
    )

    # Add columns to user
    with op.batch_alter_table("user") as batch:
        batch.add_column(sa.Column("super_admin", sa.Boolean, nullable=False, server_default="0"))
        batch.add_column(sa.Column("active_repaircafe_id", sa.Integer, nullable=True))
        batch.create_foreign_key(
            "fk_user_active_repaircafe",
            "repaircafe",
            ["active_repaircafe_id"],
            ["id"],
        )

    # Add repaircafe_id to tenant-scoped tables
    tables = [
        "repair",
        "session",
        "location",
        "note",
        "log",
        "notification",
        "sparechange",
        "message",
    ]
    for table in tables:
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("repaircafe_id", sa.Integer, nullable=True))
            batch.create_foreign_key(
                f"fk_{table}_repaircafe",
                "repaircafe",
                ["repaircafe_id"],
                ["id"],
            )

    # Drop existing unique constraint on location.name if present, then add composite
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    for uc in inspector.get_unique_constraints("location"):
        cols = uc.get("column_names") or []
        if cols == ["name"]:
            op.drop_constraint(uc["name"], "location", type_="unique")
            break
    op.create_unique_constraint("uix_location_cafe", "location", ["repaircafe_id", "name"])

    # Data migration: create default Repair Café and attach existing records
    dialect = conn.dialect.name
    default_slug = "repaircafe-orsay"
    default_name = "Repair Café Orsay"
    row = conn.execute(
        sa.text("SELECT id FROM repaircafe WHERE slug = :slug"), {"slug": default_slug}
    ).fetchone()
    if not row:
        conn.execute(
            sa.text(
                """
                INSERT INTO repaircafe (name, slug, email)
                VALUES (:name, :slug, :email)
                """
            ),
            {"name": default_name, "slug": default_slug, "email": "app@repaircafe-orsay.org"},
        )
    cafe_id = conn.execute(
        sa.text("SELECT id FROM repaircafe WHERE slug = :slug"), {"slug": default_slug}
    ).scalar()

    if cafe_id:
        user_tbl = _quote_user_table(dialect)
        # Link all users to default cafe
        conn.execute(
            sa.text(
                f"""
                INSERT INTO association_user_repaircafe (user_id, repaircafe_id, role)
                SELECT id, :cafe_id, NULL FROM {user_tbl}
                """
            ),
            {"cafe_id": cafe_id},
        )
        # Promote legacy admins as cafe admins
        if dialect == "mysql":
            conn.execute(
                sa.text(
                    f"""
                    UPDATE association_user_repaircafe aur
                    JOIN {user_tbl} u ON u.id = aur.user_id
                    SET aur.role = 'admin'
                    WHERE aur.repaircafe_id = :cafe_id AND u.admin = 1
                    """
                ),
                {"cafe_id": cafe_id},
            )
        else:
            conn.execute(
                sa.text(
                    f"""
                    UPDATE association_user_repaircafe
                    SET role = 'admin'
                    WHERE repaircafe_id = :cafe_id
                      AND user_id IN (SELECT id FROM {user_tbl} WHERE admin = 1)
                    """
                ),
                {"cafe_id": cafe_id},
            )
        # Set active cafe for all users
        conn.execute(
            sa.text(f"UPDATE {user_tbl} SET active_repaircafe_id = :cafe_id"),
            {"cafe_id": cafe_id},
        )
        # Set repaircafe_id on existing records
        for table in tables:
            conn.execute(
                sa.text(f"UPDATE {table} SET repaircafe_id = :cafe_id"),
                {"cafe_id": cafe_id},
            )


def downgrade():
    # Remove composite unique constraint for location
    op.drop_constraint("uix_location_cafe", "location", type_="unique")

    # Drop repaircafe_id from tenant-scoped tables
    tables = [
        "repair",
        "session",
        "location",
        "note",
        "log",
        "notification",
        "sparechange",
        "message",
    ]
    for table in tables:
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(f"fk_{table}_repaircafe", type_="foreignkey")
            batch.drop_column("repaircafe_id")

    # Drop user columns
    with op.batch_alter_table("user") as batch:
        batch.drop_constraint("fk_user_active_repaircafe", type_="foreignkey")
        batch.drop_column("active_repaircafe_id")
        batch.drop_column("super_admin")

    # Drop association and repaircafe tables
    op.drop_table("association_user_repaircafe")
    op.drop_table("repaircafe")
