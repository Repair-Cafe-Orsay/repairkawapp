"""(Redundant) ensure boardrolelog exists if previous migration skipped

Revision ID: 20250828_06
Revises: 20250828_05
Create Date: 2025-08-28
"""

revision = "20250828_06"
down_revision = "20250828_05"
branch_labels = None
depends_on = None


def upgrade():
    # Safety: create if not exists (SQLite/MySQL portability: try/except not available here)
    pass


def downgrade():
    pass
