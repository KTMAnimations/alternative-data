"""Add users and auth tables

Revision ID: 002_add_users_auth
Revises: 001_initial_schema
Create Date: 2024-01-02 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '002_add_users_auth'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_verified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_superuser', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
    )
    op.create_index('ix_users_email', 'users', ['email'])

    # Create refresh_tokens table
    op.create_table(
        'refresh_tokens',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('token_hash', sa.String(64), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('token_hash'),
    )
    op.create_index('ix_refresh_tokens_token_hash', 'refresh_tokens', ['token_hash'])
    op.create_index('ix_refresh_tokens_user_id', 'refresh_tokens', ['user_id'])

    # Add user_id column to api_keys table (nullable for backward compatibility)
    op.add_column('api_keys', sa.Column('user_id', sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        'fk_api_keys_user_id',
        'api_keys',
        'users',
        ['user_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_index('ix_api_keys_user_id', 'api_keys', ['user_id'])


def downgrade() -> None:
    # Remove user_id from api_keys
    op.drop_index('ix_api_keys_user_id', 'api_keys')
    op.drop_constraint('fk_api_keys_user_id', 'api_keys', type_='foreignkey')
    op.drop_column('api_keys', 'user_id')

    # Drop refresh_tokens
    op.drop_index('ix_refresh_tokens_user_id', 'refresh_tokens')
    op.drop_index('ix_refresh_tokens_token_hash', 'refresh_tokens')
    op.drop_table('refresh_tokens')

    # Drop users
    op.drop_index('ix_users_email', 'users')
    op.drop_table('users')
