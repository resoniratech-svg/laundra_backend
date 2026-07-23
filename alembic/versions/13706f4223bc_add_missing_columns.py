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

    extra_wallet_cols = [
        ('pass_file_path', sa.String(500)),
        ('apple_serial_number', sa.String(255)),
        ('apple_pass_type_identifier', sa.String(255)),
        ('apple_pass_url', sa.Text()),
        ('qr_url', sa.Text()),
        ('wallet_status', sa.String(50)),
        ('original_amount', sa.Numeric(10, 2)),
        ('remaining_balance', sa.Numeric(10, 2)),
        ('expiry_date', sa.DateTime(timezone=True)),
        ('wallet_created_at', sa.DateTime(timezone=True)),
        ('class_id', sa.String(150)),
        ('pass_status', sa.String(20)),
    ]
    for col_name, col_type in extra_wallet_cols:
        if col_name not in wallet_cols:
            op.add_column('wallet_passes', sa.Column(col_name, col_type, nullable=True))

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
