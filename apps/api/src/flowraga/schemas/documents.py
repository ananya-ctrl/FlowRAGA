import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    original_filename: str
    media_type: str
    size_bytes: int
    sha256: str
    status: str
    indexing_progress: int
    chunk_count: int
    error_message: str | None
    created_at: datetime


class IngestionJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    status: str
    attempt: int
    max_attempts: int
    progress: int
    total_chunks: int
    error_message: str | None
    created_at: datetime
