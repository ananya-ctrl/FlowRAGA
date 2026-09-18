import uuid

from pydantic import BaseModel, Field


class QuestionRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    top_k: int | None = Field(default=None, ge=1, le=20)
    similarity_threshold: float | None = Field(default=None, ge=0, le=1)
    conversation_id: uuid.UUID | None = None
    retrieval_mode: str = Field(default="hybrid", pattern="^(hybrid|vector|keyword)$")
    rerank: bool = True


class SourceResponse(BaseModel):
    label: str
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    position: int
    content: str
    score: float
    vector_rank: int | None = None
    keyword_rank: int | None = None
    rerank_score: float | None = None


class AnswerResponse(BaseModel):
    conversation_id: uuid.UUID
    message_id: uuid.UUID
    answer: str
    sources: list[SourceResponse]
    retrieval_ms: int
    generation_ms: int | None
    generation_status: str
    model: str
    trace: dict
