from pathlib import Path
import os
from dotenv import dotenv_values
from sqlalchemy.engine import make_url, URL
from alembic.config import Config
from sqlalchemy import create_engine,event
from sqlalchemy.pool import NullPool
from .backend_metadata import BACKEND

ROOT=Path(__file__).resolve().parent
class MigrationError(RuntimeError):pass

def database_url(env_file=None,environ=None):
    chosen=Path(env_file) if env_file else BACKEND/'.env'
    if env_file and not chosen.is_file():raise MigrationError('Explicit env file not found')
    values=dotenv_values(chosen,interpolate=False) if chosen.is_file() else {}
    values.update(dict(os.environ if environ is None else environ))
    raw=values.get('CAMPUS_DATABASE_URL')
    if not raw:raise MigrationError('Set CAMPUS_DATABASE_URL or provide an env file containing it')
    try:url=make_url(raw)
    except Exception:raise MigrationError('Invalid database URL; value omitted') from None
    if url.drivername not in {'sqlite','sqlite+pysqlite','mysql+pymysql'}:
        raise MigrationError('Only SQLite and MySQL+pymysql are supported')
    if not url.database or url.database==':memory:':raise MigrationError('Use a named persistent database')
    if url.drivername.startswith('sqlite'):
        if url.query:raise MigrationError('SQLite URL query parameters are unsupported')
        path=Path(url.database)
        if not path.is_absolute():path=(BACKEND/path).resolve()
        url=url.set(database=str(path))
    return url

def make_engine(url,allow_create=False):
    if url.drivername.startswith('sqlite'):
        path=Path(url.database)
        if not allow_create and not path.is_file():raise MigrationError('Database file does not exist; read-only operation refused')
        if not path.parent.is_dir():raise MigrationError('Database parent directory does not exist')
    engine=create_engine(url,poolclass=NullPool,hide_parameters=True,echo=False)
    if url.drivername.startswith('sqlite'):
        @event.listens_for(engine,'connect')
        def fk_on(connection,record):connection.execute('PRAGMA foreign_keys=ON')
    return engine

def alembic_config(connection=None,output_buffer=None):
    cfg=Config(str(ROOT/'alembic.ini'),output_buffer=output_buffer)
    cfg.attributes['managed']=True
    if connection is not None:cfg.attributes['connection']=connection
    return cfg
