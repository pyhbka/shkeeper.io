"""Add addr column to Transaction

Revision ID: ca53e1271e42
Revises: cd6076e578ca
Create Date: 2025-12-04

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ca53e1271e42'
down_revision = 'cd6076e578ca'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('transaction', schema=None) as batch_op:
        batch_op.add_column(sa.Column('addr', sa.String(), nullable=True))
        batch_op.create_index(batch_op.f('ix_transaction_addr'), ['addr'], unique=False)


def downgrade():
    with op.batch_alter_table('transaction', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_transaction_addr'))
        batch_op.drop_column('addr')
