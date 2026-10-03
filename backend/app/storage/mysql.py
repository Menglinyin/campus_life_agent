from contextlib import contextmanager
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
class Base(DeclarativeBase):
    pass
class Database:
    def __init__(self, url):
        options = {"connect_args":{"check_same_thread":False}} if url.startswith("sqlite") else {"pool_pre_ping":True,"pool_recycle":1800}
        self.engine = create_engine(url, **options)
        if url.startswith("sqlite"):
            @event.listens_for(self.engine, "connect")
            def foreign_keys(connection, _):
                connection.execute("PRAGMA foreign_keys=ON")
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)
    def initialize(self):
        from app.storage import models
        Base.metadata.create_all(self.engine)
    @contextmanager
    def transaction(self):
        with self.sessions.begin() as session:
            yield session
    def close(self):
        self.engine.dispose()
