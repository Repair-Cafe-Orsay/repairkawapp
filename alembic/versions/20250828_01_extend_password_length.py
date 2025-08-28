"""Extend password column length to 255

Revision ID: 20250828_01
Revises: 
Create Date: 2025-08-28
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250828_01'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table('user') as batch_op:
        batch_op.alter_column('password', type_=sa.String(255))


def downgrade():
    with op.batch_alter_table('user') as batch_op:
        batch_op.alter_column('password', type_=sa.String(100))
