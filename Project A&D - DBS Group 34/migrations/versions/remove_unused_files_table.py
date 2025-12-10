"""remove_unused_files_table

Revision ID: remove_files_table
Revises: 8f40f0d14d34
Create Date: 2025-12-10 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'remove_files_table'
down_revision = '8f40f0d14d34'  # Laatste migration: add_stock_price_history_and_company_info
branch_labels = None
depends_on = None


def upgrade():
    # Drop de ongebruikte 'files' tabel
    # Let op: dit is NIET de 'file_items' tabel die wel wordt gebruikt!
    op.drop_table('files')


def downgrade():
    # Herstel de 'files' tabel (indien nodig voor rollback)
    op.create_table('files',
        sa.Column('files_id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('file_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('template', sa.Text(), nullable=True),
        sa.Column('post_analyses', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('files_id')
    )

