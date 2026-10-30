"""phase2_pg_trgm

Revision ID: phase2_pg_trgm
Revises: initial_migration
Create Date: 2026-09-20 16:55:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'phase2_pg_trgm'
down_revision = 'initial_migration'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Enable pg_trgm
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
    
    # Create GIN indexes using gin_trgm_ops for partial match search
    op.execute("CREATE INDEX ix_stocks_symbol_trgm ON stocks USING GIN (symbol gin_trgm_ops);")
    op.execute("CREATE INDEX ix_stocks_name_trgm ON stocks USING GIN (name gin_trgm_ops);")

def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_stocks_name_trgm;")
    op.execute("DROP INDEX IF EXISTS ix_stocks_symbol_trgm;")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm;")
