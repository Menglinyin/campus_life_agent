"""Users, conversation history and preferences. Python defaults remain ORM-owned."""
from alembic import op
import sqlalchemy as sa
revision='0001'
down_revision=None
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('users',sa.Column('id',sa.String(64),primary_key=True))
    op.create_table('chat_sessions',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('user_id',sa.String(64),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('version',sa.Integer(),nullable=False),sa.Column('slots',sa.JSON(),nullable=False))
    op.create_index('ix_chat_sessions_user_id','chat_sessions',['user_id'])
    op.create_table('chat_messages',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('session_id',sa.String(36),sa.ForeignKey('chat_sessions.id'),nullable=False),
        sa.Column('role',sa.String(16),nullable=False),sa.Column('content',sa.Text(),nullable=False),
        sa.Column('payload',sa.JSON(),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_chat_messages_session_id','chat_messages',['session_id'])
    op.create_table('user_preferences',sa.Column('user_id',sa.String(64),sa.ForeignKey('users.id'),primary_key=True),
        sa.Column('values',sa.JSON(),nullable=False))

def downgrade():
    op.drop_table('user_preferences')
    op.drop_index('ix_chat_messages_session_id',table_name='chat_messages');op.drop_table('chat_messages')
    op.drop_index('ix_chat_sessions_user_id',table_name='chat_sessions');op.drop_table('chat_sessions')
    op.drop_table('users')
