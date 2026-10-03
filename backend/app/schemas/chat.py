from datetime import date as Date
from uuid import UUID
from pydantic import BaseModel,Field
class ChatRequest(BaseModel):
    message: str = Field(min_length=1,max_length=2000)
    session_id: UUID | None = None
    date: Date | None = None
class ChatResponse(BaseModel):
    session_id: str
    message_id: str
    answer: str
    results: list[dict]
    mode: str
