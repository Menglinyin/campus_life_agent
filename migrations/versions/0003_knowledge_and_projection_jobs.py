"""Knowledge source chunks and the existing projection-job placeholder table."""
from alembic import op
import sqlalchemy as sa
revision='0003'
down_revision='0002'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('knowledge_chunks',sa.Column('id',sa.String(64),primary_key=True),
        sa.Column('source',sa.String(255),nullable=False),sa.Column('owner',sa.String(64),nullable=False),
        sa.Column('text',sa.Text(),nullable=False))
    op.create_index('ix_knowledge_chunks_owner','knowledge_chunks',['owner'])
    op.create_table('projection_jobs',sa.Column('id',sa.String(64),primary_key=True),
        sa.Column('payload',sa.JSON(),nullable=False),sa.Column('status',sa.String(16),nullable=False))

def downgrade():
    op.drop_table('projection_jobs')
    op.drop_index('ix_knowledge_chunks_owner',table_name='knowledge_chunks');op.drop_table('knowledge_chunks')
