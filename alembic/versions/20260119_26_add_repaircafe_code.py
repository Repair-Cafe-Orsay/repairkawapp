"""Add RepairCafe code (acronym)

Revision ID: 20260119_26
Revises: 20260119_25
Create Date: 2026-01-19
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260119_26"
down_revision = "20260119_25"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col["name"] for col in inspector.get_columns("repaircafe")]
    if "code" not in columns:
        with op.batch_alter_table("repaircafe") as batch:
            batch.add_column(sa.Column("code", sa.String(10), nullable=True))
    # Set default code for Orsay and fallback to slug
    conn.execute(
        sa.text(
            """
            UPDATE repaircafe
            SET code = CASE
                WHEN slug = 'repaircafe-orsay' THEN 'rco'
                WHEN code IS NULL THEN slug
                ELSE code
            END
            """
        )
    )
    with op.batch_alter_table("repaircafe") as batch:
        batch.alter_column("code", existing_type=sa.String(10), nullable=False)
        if "uix_repaircafe_code" not in {
            uc["name"] for uc in inspector.get_unique_constraints("repaircafe")
        }:
            batch.create_unique_constraint("uix_repaircafe_code", ["code"])


def downgrade():
    with op.batch_alter_table("repaircafe") as batch:
        batch.drop_constraint("uix_repaircafe_code", type_="unique")
        batch.drop_column("code")
