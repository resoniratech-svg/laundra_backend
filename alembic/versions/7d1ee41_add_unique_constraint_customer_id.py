"""add_unique_constraint_to_wallet_passes_customer_id

Revision ID: 7d1ee41_unique_cust
Revises: 13706f4223bc
Create Date: 2026-07-29

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision: str = '7d1ee41_unique_cust'
down_revision: Union[str, Sequence[str], None] = '13706f4223bc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Pure schema change only - Add UNIQUE(customer_id) constraint to wallet_passes."""
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    
    # Check if constraint already exists to be idempotent
    constraints = [c['name'] for c in inspector.get_unique_constraints('wallet_passes')]
    if 'wallet_passes_customer_id_key' not in constraints:
        op.create_unique_constraint(
            'wallet_passes_customer_id_key',
            'wallet_passes',
            ['customer_id']
        )


def downgrade() -> None:
    """Drop UNIQUE(customer_id) constraint from wallet_passes."""
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    constraints = [c['name'] for c in inspector.get_unique_constraints('wallet_passes')]
    if 'wallet_passes_customer_id_key' in constraints:
        op.drop_constraint('wallet_passes_customer_id_key', 'wallet_passes', type_='unique')
