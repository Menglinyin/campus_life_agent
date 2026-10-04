from datetime import date as Date
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from . import backend  # noqa: F401
from app.schemas.tools import ToolArgs

class Row(BaseModel):
    model_config=ConfigDict(extra='ignore',allow_inf_nan=False)
    id: str=Field(min_length=1,max_length=64)
    name: str=Field(min_length=1,max_length=200)
class ClassroomRow(Row):
    date: Date
    available: bool
    seats: int=Field(ge=0,le=10000)
class CourseRow(Row):
    date: Date
    room: str=Field(min_length=1,max_length=200)
    time: str=Field(pattern=r'^([01]\d|2[0-3]):[0-5]\d$')
    auditing_allowed: bool
class DishRow(Row):
    date: Date
    price: float=Field(ge=0,le=10000)
    spice: int=Field(ge=0,le=2)
    vegetarian: bool
    rating: float=Field(ge=0,le=5)
    available: bool
class SecondhandRow(Row):
    price: float=Field(ge=0,le=100000)
    status: Literal['active','reserved','sold','withdrawn']
class FeedbackArgs(BaseModel):
    model_config=ConfigDict(extra='forbid')
    target_kind: Literal['classrooms','courses','dishes','secondhand']
    target_id: str=Field(min_length=1,max_length=64,pattern=r'^[A-Za-z0-9_.:-]+$')
    rating: int=Field(ge=1,le=5)
    comment: str=Field('',max_length=500)
    idempotency_key: str=Field(min_length=8,max_length=128,pattern=r'^[A-Za-z0-9_.:-]+$')
