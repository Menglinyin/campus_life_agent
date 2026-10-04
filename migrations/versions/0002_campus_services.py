"""Campus business tables with the current id + JSON payload contract."""
from alembic import op
import sqlalchemy as sa
revision='0002'
down_revision='0001'
branch_labels=None
depends_on=None

def upgrade():
    for name in ('classrooms','courses','dishes','secondhand'):
        op.create_table(name,sa.Column('id',sa.String(64),primary_key=True),sa.Column('payload',sa.JSON(),nullable=False))

def downgrade():
    for name in ('secondhand','dishes','courses','classrooms'):op.drop_table(name)
