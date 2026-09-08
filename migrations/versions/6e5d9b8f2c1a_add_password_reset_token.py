"""add one-time password reset token hash

Revision ID: 6e5d9b8f2c1a
Revises: b14fd9ebf51e
"""
from alembic import op
import sqlalchemy as sa


revision = "6e5d9b8f2c1a"
down_revision = "b14fd9ebf51e"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("password_reset_token_hash", sa.String(length=64), nullable=True))


def downgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("password_reset_token_hash")