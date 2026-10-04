"""Feedback table used by the MCP review/idempotency implementation."""
from alembic import op
import sqlalchemy as sa
revision='0004'
down_revision='0003'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('feedback',sa.Column('id',sa.String(64),primary_key=True),sa.Column('payload',sa.JSON(),nullable=False))

def downgrade():op.drop_table('feedback')
