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
    error_message: str | None
    created_at: datetime
