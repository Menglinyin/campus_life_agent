from uuid import UUID
from pydantic import BaseModel
class SpeechRequest(BaseModel):
    message_id: UUID
