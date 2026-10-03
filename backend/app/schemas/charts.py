from uuid import UUID
from pydantic import BaseModel
class ChartRequest(BaseModel):
    message_id: UUID
