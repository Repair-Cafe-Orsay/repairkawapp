"""add object type / variant / subtype hierarchy

Revision ID: 20250830_10
Revises: 20250830_09
Create Date: 2025-08-30
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20250830_10"
down_revision = "20250830_09"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "object_type",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("category.id"), nullable=False),
    )
    op.create_index("idx_object_type_category", "object_type", ["category_id"])  # perf

    op.create_table(
        "object_variant",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column(
            "object_type_id",
            sa.Integer(),
            sa.ForeignKey("object_type.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )

    op.create_table(
        "object_subtype",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column(
            "object_type_id",
            sa.Integer(),
            sa.ForeignKey("object_type.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )

    # Ajout des FK optionnelles sur repair
    with op.batch_alter_table("repair") as batch_op:
        batch_op.add_column(
            sa.Column(
                "object_type_id", sa.Integer(), sa.ForeignKey("object_type.id"), nullable=True
            )
        )
        batch_op.add_column(
            sa.Column(
                "object_subtype_id", sa.Integer(), sa.ForeignKey("object_subtype.id"), nullable=True
            )
        )


def downgrade():
    with op.batch_alter_table("repair") as batch_op:
        batch_op.drop_constraint(None, type_="foreignkey")  # laisser Alembic résoudre
        batch_op.drop_column("object_subtype_id")
        batch_op.drop_column("object_type_id")

    op.drop_table("object_subtype")
    op.drop_table("object_variant")
    op.drop_index("idx_object_type_category", table_name="object_type")
    op.drop_table("object_type")
