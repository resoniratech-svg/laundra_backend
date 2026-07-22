"""add_missing_columns

Revision ID: 13706f4223bc
Revises: 
Create Date: 2026-07-22 17:16:40.219691

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '13706f4223bc'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


from sqlalchemy.dialects import postgresql
from sqlalchemy.engine.reflection import Inspector

def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)

    # Check and Add tenant_id to wallet_passes
    wallet_cols = [c['name'] for c in inspector.get_columns('wallet_passes')]
    if 'tenant_id' not in wallet_cols:
        op.add_column('wallet_passes', sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=True))
        op.create_foreign_key('fk_wallet_passes_tenant_id', 'wallet_passes', 'companies', ['tenant_id'], ['id'], ondelete='CASCADE')
        op.create_index('ix_wallet_passes_tenant_id', 'wallet_passes', ['tenant_id'])

    # Check and Add applied_package_id to orders
    order_cols = [c['name'] for c in inspector.get_columns('orders')]
    if 'applied_package_id' not in order_cols:
        op.add_column('orders', sa.Column('applied_package_id', postgresql.UUID(as_uuid=True), nullable=True))
        op.create_foreign_key('fk_orders_applied_package_id', 'orders', 'customer_packages', ['applied_package_id'], ['id'])

def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_orders_applied_package_id', 'orders', type_='foreignkey')
    op.drop_column('orders', 'applied_package_id')

    op.drop_index('ix_wallet_passes_tenant_id', table_name='wallet_passes')
    op.drop_constraint('fk_wallet_passes_tenant_id', 'wallet_passes', type_='foreignkey')
    op.drop_column('wallet_passes', 'tenant_id')
