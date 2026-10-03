from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.storage.mysql import Base
class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source: Mapped[str] = mapped_column(String(255))
    owner: Mapped[str] = mapped_column(String(64), default="public", index=True)
    text: Mapped[str] = mapped_column(Text)
