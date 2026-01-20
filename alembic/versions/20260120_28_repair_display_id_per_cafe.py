"""Make repair display_id unique per cafe

Revision ID: 20260120_28
Revises: 20260120_27
Create Date: 2026-01-20
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260120_28"
down_revision = "20260120_27"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    for uc in inspector.get_unique_constraints("repair"):
        cols = uc.get("column_names") or []
        if cols == ["display_id"]:
            op.drop_constraint(uc["name"], "repair", type_="unique")
            break
    op.create_unique_constraint(
        "uix_repair_display_id_cafe",
        "repair",
        ["repaircafe_id", "display_id"],
    )


def downgrade():
    op.drop_constraint("uix_repair_display_id_cafe", "repair", type_="unique")
    op.create_unique_constraint("uix_repair_display_id", "repair", ["display_id"])
