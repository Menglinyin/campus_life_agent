from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from app.storage.mysql import Base
class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
