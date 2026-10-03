from datetime import date as Date
from pydantic import BaseModel, ConfigDict, Field
class ToolArgs(BaseModel):
    model_config=ConfigDict(extra="forbid")
    date: Date | None = None
    query: str = Field("",max_length=1000)
    budget: float | None = Field(None,ge=0,le=1000)
    spice: int | None = Field(None,ge=0,le=2)
    vegetarian: bool | None = None
