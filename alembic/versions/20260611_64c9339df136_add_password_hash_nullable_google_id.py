"""add_password_hash_nullable_google_id

Revision ID: 64c9339df136
Revises: 2d82416e6533
Create Date: 2026-06-11 01:27:36.042075

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '64c9339df136'
down_revision: Union[str, None] = '2d82416e6533'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite doesn't support ALTER COLUMN, so use batch mode (table rebuild).
    with op.batch_alter_table('users', recreate='always') as batch_op:
        batch_op.add_column(sa.Column('password_hash', sa.String(length=255), nullable=True))
        batch_op.alter_column('google_id', existing_type=sa.String(128), nullable=True)
        batch_op.create_index('ix_users_email_unique', ['email'], unique=True)


def downgrade() -> None:
    with op.batch_alter_table('users', recreate='always') as batch_op:
        batch_op.drop_column('password_hash')
        batch_op.alter_column('google_id', existing_type=sa.String(128), nullable=False)
        batch_op.drop_index('ix_users_email_unique')
