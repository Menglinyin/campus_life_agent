from sqlalchemy import String, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.storage.mysql import Base
class Preference(Base):
    __tablename__="user_preferences"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    values: Mapped[dict] = mapped_column(JSON, default=dict)
