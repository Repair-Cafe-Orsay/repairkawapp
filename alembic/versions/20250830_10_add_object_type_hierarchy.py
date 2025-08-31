"""add object_type hierarchy + category.icon_name

Revision ID: 20250830_10
Revises: 20250830_09
Create Date: 2025-08-30
"""

from alembic import op
import sqlalchemy as sa


revision = "20250830_10"
down_revision = "20250830_09"
branch_labels = None
depends_on = None


def upgrade():
    # Ajout colonne icon_name dans category (nullable)
    with op.batch_alter_table("category") as batch_op:
        batch_op.add_column(sa.Column("icon_name", sa.String(length=50), nullable=True))

    # Table object_type
    op.create_table(
        "object_type",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["category.id"], ondelete=None),
    )
    op.create_index("idx_object_type_category", "object_type", ["category_id"])
    op.create_unique_constraint(
        "uix_object_type_name_category", "object_type", ["name", "category_id"]
    )

    # Table object_variant
    op.create_table(
        "object_variant",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("object_type_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["object_type_id"], ["object_type.id"], ondelete="CASCADE"),
    )

    # Table object_subtype
    op.create_table(
        "object_subtype",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("object_type_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["object_type_id"], ["object_type.id"], ondelete="CASCADE"),
    )


def downgrade():
    # Drop tables in reverse dependency order
    op.drop_table("object_subtype")
    op.drop_table("object_variant")
    op.drop_constraint("uix_object_type_name_category", "object_type", type_="unique")
    op.drop_index("idx_object_type_category", table_name="object_type")
    op.drop_table("object_type")

    with op.batch_alter_table("category") as batch_op:
        batch_op.drop_column("icon_name")
