"""dummy sync: visibility_public_trombi already mapped to existing public_trombi

Revision ID: 20250831_13
Revises: 20250831_11
Create Date: 2025-08-31
"""

revision = "20250831_13"
down_revision = "20250831_11"
branch_labels = None
depends_on = None


def upgrade():
    # No-op: colonne legacy déjà en place.
    pass


def downgrade():
    pass
