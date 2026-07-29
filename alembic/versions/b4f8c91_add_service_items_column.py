"""Add service_items JSONB column to customer_packages

Revision ID: b4f8c91_service_items
Revises: a3f9e82
Create Date: 2026-07-29

Adds dynamic JSONB column service_items to customer_packages table
for storing service-level item balances (e.g. Wash & Press, Dry Clean).
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision: str = 'b4f8c91_service_items'
down_revision: Union[str, Sequence[str], None] = 'a3f9e82'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add service_items JSONB column to customer_packages if not present."""
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    cp_cols = [c['name'] for c in inspector.get_columns('customer_packages')]
    if 'service_items' not in cp_cols:
        op.add_column(
            'customer_packages',
            sa.Column('service_items', postgresql.JSONB(astext_type=sa.Text()), nullable=True)
        )


def downgrade() -> None:
    """Drop service_items column from customer_packages."""
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    cp_cols = [c['name'] for c in inspector.get_columns('customer_packages')]
    if 'service_items' in cp_cols:
        op.drop_column('customer_packages', 'service_items')
