"""Add per-cafe membership on association table.

Revision ID: 20260120_31
Revises: 20260120_30
Create Date: 2026-01-20
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260120_31"
down_revision = "20260120_30"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "association_user_repaircafe",
        sa.Column("last_membership", sa.Integer(), nullable=True),
    )
    op.add_column(
        "membershiplog",
        sa.Column("repaircafe_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_membershiplog_repaircafe",
        "membershiplog",
        "repaircafe",
        ["repaircafe_id"],
        ["id"],
    )

    # Migrer la cotisation globale vers la cotisation par café
    bind = op.get_bind()
    assoc = sa.table(
        "association_user_repaircafe",
        sa.column("user_id", sa.Integer()),
        sa.column("last_membership", sa.Integer()),
    )
    user = sa.table(
        "user",
        sa.column("id", sa.Integer()),
        sa.column("last_membership", sa.Integer()),
    )
    subq = sa.select(user.c.last_membership).where(user.c.id == assoc.c.user_id).scalar_subquery()
    bind.execute(assoc.update().values(last_membership=subq))


def downgrade():
    op.drop_constraint("fk_membershiplog_repaircafe", "membershiplog", type_="foreignkey")
    op.drop_column("membershiplog", "repaircafe_id")
    op.drop_column("association_user_repaircafe", "last_membership")
