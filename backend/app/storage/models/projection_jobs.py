from sqlalchemy import String, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.storage.mysql import Base
class ProjectionJob(Base):
    __tablename__="projection_jobs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(16), default="pending")
