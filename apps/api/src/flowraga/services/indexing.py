from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from flowraga.core.config import Settings
from flowraga.db.models import Document, DocumentChunk, IngestionJob
from flowraga.models.providers import EmbeddingProvider


@dataclass(frozen=True)
class TextChunk:
    position: int
    content: str
    token_count: int


def chunk_text(text: str, size: int, overlap: int) -> list[TextChunk]:
    words = text.split()
    if not words:
        return []
    chunks = []
    step = size - overlap
    for start in range(0, len(words), step):
        selected = words[start : start + size]
        if not selected:
            break
        chunks.append(TextChunk(len(chunks), " ".join(selected), len(selected)))
        if start + size >= len(words):
            break
    return chunks


async def index_document(
    db: AsyncSession,
    job: IngestionJob,
    provider: EmbeddingProvider,
    settings: Settings,
    persist_progress: bool = False,
) -> int:
    document = await db.scalar(select(Document).where(Document.id == job.document_id))
    if document is None:
        raise ValueError("Document no longer exists")
    chunks = chunk_text(
        document.extracted_text or "", settings.chunk_size_words, settings.chunk_overlap_words
    )
    if not chunks:
        raise ValueError("Document contains no indexable text")
    job.total_chunks = len(chunks)
    job.progress = 0
    document.status = "indexing"
    document.indexing_progress = 0
    await db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
    if persist_progress:
        await db.commit()
    for batch_start in range(0, len(chunks), settings.embedding_batch_size):
        batch = chunks[batch_start : batch_start + settings.embedding_batch_size]
        vectors = await provider.embed_documents([chunk.content for chunk in batch])
        if len(vectors) != len(batch) or any(
            len(vector) != provider.dimensions for vector in vectors
        ):
            raise ValueError("Embedding provider returned an invalid vector shape")
        db.add_all(
            [
                DocumentChunk(
                    document_id=document.id,
                    project_id=document.project_id,
                    owner_id=document.owner_id,
                    position=chunk.position,
                    content=chunk.content,
                    token_count=chunk.token_count,
                    embedding=vector,
                )
                for chunk, vector in zip(batch, vectors, strict=True)
            ]
        )
        job.progress = min(batch_start + len(batch), len(chunks))
        document.indexing_progress = round(job.progress / len(chunks) * 100)
        await db.flush()
        if persist_progress:
            await db.commit()
    document.status = "ready"
    document.indexing_progress = 100
    document.chunk_count = len(chunks)
    document.error_message = None
    return len(chunks)
