from sqlalchemy import String, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.storage.mysql import Base
class Classroom(Base):
    __tablename__="classrooms"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON)
