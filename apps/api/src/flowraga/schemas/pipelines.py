import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from flowraga.services.pipeline_validation import validate_pipeline_graph


class PipelineNode(BaseModel):
    id: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    type: Literal["source", "chunk", "embed", "retrieve", "rerank", "generate", "evaluate"]
    label: str = Field(min_length=1, max_length=80)
    x: float = Field(default=0, ge=-5000, le=5000)
    y: float = Field(default=0, ge=-5000, le=5000)


class PipelineEdge(BaseModel):
    id: str = Field(min_length=1, max_length=128)
    source: str = Field(min_length=1, max_length=64)
    target: str = Field(min_length=1, max_length=64)


class PipelineConfiguration(BaseModel):
    retrieval_mode: str = Field(default="hybrid", pattern="^(hybrid|vector|keyword)$")
    top_k: int = Field(default=5, ge=1, le=20)
    similarity_threshold: float = Field(default=0.25, ge=0, le=1)
    rerank: bool = True
    chunk_size_words: int = Field(default=350, ge=50, le=2000)
    chunk_overlap_words: int = Field(default=50, ge=0, le=500)
    generation_model: str = Field(default="qwen2.5:3b", min_length=1, max_length=120)
    nodes: list[PipelineNode] = Field(default_factory=list, max_length=30)
    edges: list[PipelineEdge] = Field(default_factory=list, max_length=60)

    @model_validator(mode="after")
    def validate_graph(self) -> "PipelineConfiguration":
        if self.chunk_overlap_words >= self.chunk_size_words:
            raise ValueError("Chunk overlap must be smaller than chunk size")
        if self.nodes:
            validate_pipeline_graph(self.nodes, self.edges)
        return self


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
