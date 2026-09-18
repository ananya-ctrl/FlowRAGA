import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PipelineConfiguration(BaseModel):
    retrieval_mode: str = Field(default="hybrid", pattern="^(hybrid|vector|keyword)$")
    top_k: int = Field(default=5, ge=1, le=20)
    similarity_threshold: float = Field(default=0.25, ge=0, le=1)
    rerank: bool = True


class PipelineCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    configuration: PipelineConfiguration = Field(default_factory=PipelineConfiguration)


class PipelineUpdate(PipelineCreate):
    pass


class PipelineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    version: int
    is_active: bool
    configuration: PipelineConfiguration
    created_at: datetime
    updated_at: datetime


class PipelineImport(BaseModel):
    pipelines: list[PipelineCreate] = Field(min_length=1, max_length=25)
