from datetime import datetime, timezone
from sqlalchemy import String, Text, JSON, ForeignKey, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column
from app.storage.mysql import Base
def now(): return datetime.now(timezone.utc)
class Conversation(Base):
    __tablename__ = "chat_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=0)
    slots: Mapped[dict] = mapped_column(JSON, default=dict)
class Message(Base):
    __tablename__ = "chat_messages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("chat_sessions.id"), index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
