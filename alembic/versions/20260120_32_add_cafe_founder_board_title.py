"""Add per-cafe founder and board role.

Revision ID: 20260120_32
Revises: 20260120_31
Create Date: 2026-01-20
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260120_32"
down_revision = "20260120_31"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "association_user_repaircafe",
        sa.Column("founder", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "association_user_repaircafe",
        sa.Column("board_title", sa.String(30), nullable=True),
    )
    op.add_column(
        "boardrolelog",
        sa.Column("repaircafe_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_boardrolelog_repaircafe",
        "boardrolelog",
        "repaircafe",
        ["repaircafe_id"],
        ["id"],
    )

    # Migrer les champs globaux vers l'association par café
    bind = op.get_bind()
    assoc = sa.table(
        "association_user_repaircafe",
        sa.column("user_id", sa.Integer()),
        sa.column("founder", sa.Boolean()),
        sa.column("board_title", sa.String(30)),
    )
    user = sa.table(
        "user",
        sa.column("id", sa.Integer()),
        sa.column("founder", sa.Boolean()),
        sa.column("board_title", sa.String(30)),
    )
    sub_founder = sa.select(user.c.founder).where(user.c.id == assoc.c.user_id).scalar_subquery()
    sub_board = sa.select(user.c.board_title).where(user.c.id == assoc.c.user_id).scalar_subquery()
    bind.execute(assoc.update().values(founder=sub_founder, board_title=sub_board))

    boardrolelog = sa.table(
        "boardrolelog",
        sa.column("user_id", sa.Integer()),
        sa.column("repaircafe_id", sa.Integer()),
    )
    assoc_rc = sa.table(
        "association_user_repaircafe",
        sa.column("user_id", sa.Integer()),
        sa.column("repaircafe_id", sa.Integer()),
    )
    sub_rc = (
        sa.select(sa.func.min(assoc_rc.c.repaircafe_id))
        .where(assoc_rc.c.user_id == boardrolelog.c.user_id)
        .scalar_subquery()
    )
    bind.execute(
        boardrolelog.update()
        .where(boardrolelog.c.repaircafe_id.is_(None))
        .values(repaircafe_id=sub_rc)
    )


def downgrade():
    op.drop_constraint("fk_boardrolelog_repaircafe", "boardrolelog", type_="foreignkey")
    op.drop_column("boardrolelog", "repaircafe_id")
    op.drop_column("association_user_repaircafe", "board_title")
    op.drop_column("association_user_repaircafe", "founder")
