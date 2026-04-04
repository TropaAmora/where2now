"""add tenant_id to clients and delivery_points

Revision ID: e7abeeb17928
Revises: bc9f7add114f
Create Date: 2026-04-04 16:45:03.710427

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e7abeeb17928'
down_revision = 'bc9f7add114f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # server_default='default' backfills existing rows and satisfies NOT NULL for SQLite,
    # which cannot add a NOT NULL column without a default value.
    op.add_column('clients', sa.Column(
        'tenant_id', sa.String(length=64), nullable=False, server_default='default'
    ))
    op.create_index(op.f('ix_clients_tenant_id'), 'clients', ['tenant_id'], unique=False)

    op.add_column('delivery_points', sa.Column(
        'tenant_id', sa.String(length=64), nullable=False, server_default='default'
    ))
    op.create_index(op.f('ix_delivery_points_tenant_id'), 'delivery_points', ['tenant_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_delivery_points_tenant_id'), table_name='delivery_points')
    op.drop_column('delivery_points', 'tenant_id')
    op.drop_index(op.f('ix_clients_tenant_id'), table_name='clients')
    op.drop_column('clients', 'tenant_id')
