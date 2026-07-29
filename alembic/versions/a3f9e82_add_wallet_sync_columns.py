"""Add wallet_sync_status, wallet_sync_error, wallet_sync_attempts columns

Revision ID: a3f9e82
Revises: 7d1ee41
Create Date: 2026-07-29

Adds APNs sync tracking columns to wallet_passes for async background
push notification retry mechanism.
"""
from alembic import op
import sqlalchemy as sa

revision = 'a3f9e82'
down_revision = '7d1ee41_unique_cust'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('wallet_passes', sa.Column('wallet_sync_status', sa.String(20), nullable=True, server_default='SYNCED'))
    op.add_column('wallet_passes', sa.Column('wallet_sync_error', sa.Text(), nullable=True))
    op.add_column('wallet_passes', sa.Column('wallet_sync_attempts', sa.Integer(), nullable=True, server_default='0'))

def downgrade() -> None:
    op.drop_column('wallet_passes', 'wallet_sync_attempts')
    op.drop_column('wallet_passes', 'wallet_sync_error')
    op.drop_column('wallet_passes', 'wallet_sync_status')
