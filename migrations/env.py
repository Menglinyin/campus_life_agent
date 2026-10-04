"""Managed Alembic environment; never reads a default URL or logs credentials."""
from alembic import context
from migrations.backend_metadata import metadata
from migrations.config import MigrationError

config=context.config
if not config.attributes.get('managed'):
    raise MigrationError('Use python -m migrations.manage; direct online Alembic execution is disabled')

if context.is_offline_mode():
    dialect=config.attributes['offline_dialect']
    context.configure(dialect_name=dialect,target_metadata=metadata,literal_binds=True,compare_type=True,compare_server_default=True)
    with context.begin_transaction():context.run_migrations()
else:
    connection=config.attributes.get('connection')
    if connection is None:raise MigrationError('A managed database connection is required')
    context.configure(connection=connection,target_metadata=metadata,compare_type=True,compare_server_default=True,
                      render_as_batch=connection.dialect.name=='sqlite')
    with context.begin_transaction():context.run_migrations()
