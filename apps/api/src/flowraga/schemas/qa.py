import uuid

from pydantic import BaseModel, Field


class QuestionRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    top_k: int | None = Field(default=None, ge=1, le=20)
    similarity_threshold: float | None = Field(default=None, ge=0, le=1)


class SourceResponse(BaseModel):
    label: str
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    position: int
    content: str
    score: float


class AnswerResponse(BaseModel):
    answer: str
    sources: list[SourceResponse]
    retrieval_ms: int
    generation_ms: int | None
    generation_status: str
    model: str
