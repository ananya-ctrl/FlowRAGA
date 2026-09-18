import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    role: str
    content: str
    sources: list[dict] | None
    trace: dict | None
    created_at: datetime


class ConversationDetail(ConversationResponse):
    messages: list[MessageResponse]


class FeedbackRequest(BaseModel):
    rating: Literal[-1, 1]
    comment: str | None = Field(default=None, max_length=1000)


class FeedbackResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    message_id: uuid.UUID
    rating: int
    comment: str | None
