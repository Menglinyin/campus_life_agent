from sqlalchemy import inspect,UniqueConstraint,CheckConstraint
from alembic.migration import MigrationContext
from alembic.autogenerate import compare_metadata
from alembic.script import ScriptDirectory
from .backend_metadata import metadata
from .config import MigrationError,alembic_config

VERSION_TABLE='alembic_version'
def heads(connection):return tuple(MigrationContext.configure(connection).get_current_heads())
def head_revision():return ScriptDirectory.from_config(alembic_config()).get_current_head()
def tables(connection):return set(inspect(connection).get_table_names())-{VERSION_TABLE}
def assert_known_revision(connection):
    found=heads(connection)
    if len(found)>1:raise MigrationError('Multiple database revisions are unsupported')
    if found:
        try:ScriptDirectory.from_config(alembic_config()).get_revision(found[0])
        except Exception:raise MigrationError('Database revision is not in this migration history') from None
    return found

def schema_issues(connection):
    # Compare types, nullability, columns, indexes, FKs and actual server defaults.
    context=MigrationContext.configure(connection,opts={'compare_type':True,'compare_server_default':True})
    issues=[]
    def visit(value):
        if isinstance(value,list):
            for item in value:visit(item)
        elif isinstance(value,tuple):issues.append(str(value[0]))
    for diff in compare_metadata(context,metadata):visit(diff)
    inspector=inspect(connection)
    present=tables(connection)
    for name,table in metadata.tables.items():
        if name not in present:continue
        actual=inspector.get_pk_constraint(name).get('constrained_columns',[])
        expected=[column.name for column in table.primary_key.columns]
        if actual!=expected:issues.append('primary_key:'+name)
        # Alembic doesn't cover all PK/check/unique changes; enforce baseline shape.
        compact=lambda sql:' '.join(str(sql).split()).lower()
        actual_checks={compact(item['sqltext']) for item in inspector.get_check_constraints(name)}
        expected_checks={compact(item.sqltext) for item in table.constraints if isinstance(item,CheckConstraint)}
        if actual_checks!=expected_checks:issues.append('check_constraint:'+name)
        actual_unique={tuple(item['column_names']) for item in inspector.get_unique_constraints(name)}
        actual_unique.update(tuple(item['column_names']) for item in inspector.get_indexes(name) if item.get('unique'))
        expected_unique={tuple(column.name for column in item.columns) for item in table.constraints if isinstance(item,UniqueConstraint)}
        expected_unique.update(tuple(column.name for column in item.columns) for item in table.indexes if item.unique)
        if actual_unique!=expected_unique:issues.append('unique_constraint:'+name)
    if connection.dialect.name=='sqlite':
        if connection.exec_driver_sql('PRAGMA foreign_key_check').first() is not None:
            issues.append('foreign_key_data_violation')
    return sorted(set(issues))

def preflight_upgrade(connection):
    found=assert_known_revision(connection)
    if not found and tables(connection):
        raise MigrationError('Unversioned non-empty database: use adopt-existing after schema inspection')
    if found==(head_revision(),) and schema_issues(connection):
        raise MigrationError('Head revision has schema drift; check before upgrading')

def adopt_existing(connection):
    if assert_known_revision(connection):raise MigrationError('Database already has a revision; adoption refused')
    issues=schema_issues(connection)
    if issues:raise MigrationError('Existing schema does not match the backend: '+', '.join(issues))
    return head_revision()
