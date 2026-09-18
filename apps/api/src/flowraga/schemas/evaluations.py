import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DatasetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2000)


class DatasetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime


class CaseCreate(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    expected_answer: str | None = Field(default=None, max_length=10000)
    expected_document_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)


class CaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    dataset_id: uuid.UUID
    question: str
    expected_answer: str | None
    expected_document_ids: list[str]
    created_at: datetime


class RunCreate(BaseModel):
    retrieval_mode: str = Field(default="hybrid", pattern="^(hybrid|vector|keyword)$")
    top_k: int = Field(default=5, ge=1, le=20)
    similarity_threshold: float = Field(default=0.25, ge=0, le=1)


class RunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    dataset_id: uuid.UUID
    status: str
    configuration: dict
    summary: dict | None
    progress: int
    error_message: str | None
    created_at: datetime


class ResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    case_id: uuid.UUID
    answer: str
    sources: list[dict]
    metrics: dict
    trace: dict


class RunDetail(RunResponse):
    results: list[ResultResponse]
