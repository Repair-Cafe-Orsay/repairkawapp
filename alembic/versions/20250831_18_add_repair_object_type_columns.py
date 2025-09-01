"""add object_type_id & object_subtype_id to repair

Revision ID: 20250831_18
Revises: 20250831_17
Create Date: 2025-08-31
"""

from alembic import op
import sqlalchemy as sa

revision = "20250831_18"
down_revision = "20250831_17"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    res = conn.execute(sa.text("SHOW COLUMNS FROM `repair`"))
    existing = {row[0] for row in res}

    if "object_type_id" not in existing:
        op.add_column("repair", sa.Column("object_type_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            "fk_repair_object_type",
            "repair",
            "object_type",
            ["object_type_id"],
            ["id"],
            ondelete=None,
        )
        op.create_index("idx_repair_object_type", "repair", ["object_type_id"])

    if "object_subtype_id" not in existing:
        op.add_column("repair", sa.Column("object_subtype_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            "fk_repair_object_subtype",
            "repair",
            "object_subtype",
            ["object_subtype_id"],
            ["id"],
            ondelete=None,
        )
        op.create_index("idx_repair_object_subtype", "repair", ["object_subtype_id"])


def downgrade():
    conn = op.get_bind()
    # Drop subtype first (no dependency from type column)
    res = conn.execute(sa.text("SHOW COLUMNS FROM `repair` LIKE 'object_subtype_id'"))
    if res.fetchone():
        # index may or may not exist depending on upgrade path
        try:
            op.drop_index("idx_repair_object_subtype", table_name="repair")
        except Exception:
            pass
        try:
            op.drop_constraint("fk_repair_object_subtype", "repair", type_="foreignkey")
        except Exception:
            pass
        op.drop_column("repair", "object_subtype_id")

    res = conn.execute(sa.text("SHOW COLUMNS FROM `repair` LIKE 'object_type_id'"))
    if res.fetchone():
        try:
            op.drop_index("idx_repair_object_type", table_name="repair")
        except Exception:
            pass
        try:
            op.drop_constraint("fk_repair_object_type", "repair", type_="foreignkey")
        except Exception:
            pass
        op.drop_column("repair", "object_type_id")
