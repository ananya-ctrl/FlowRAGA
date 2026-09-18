import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select

from flowraga.core.config import Settings, get_settings
from flowraga.core.database import Database
from flowraga.db.models import Document, DocumentChunk, IngestionJob
from flowraga.models.embeddings import FastEmbedProvider
from flowraga.models.providers import EmbeddingProvider
from flowraga.services.indexing import index_document


async def run_job(
    db,
    job: IngestionJob,
    provider: EmbeddingProvider,
    settings: Settings,
    persist_progress: bool = False,
) -> bool:
    document = await db.scalar(select(Document).where(Document.id == job.document_id))
    if document is None:
        job.status = "failed"
        job.error_message = "Document no longer exists"
        job.finished_at = datetime.now(UTC)
        return False
    job.status = "running"
    job.attempt += 1
    job.started_at = datetime.now(UTC)
    try:
        await index_document(db, job, provider, settings, persist_progress)
    except Exception as exc:
        await db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
        message = str(exc)[:500] or "Indexing failed"
        job.error_message = message
        document.error_message = message
        document.indexing_progress = 0
        if job.attempt < job.max_attempts:
            job.status = "queued"
            document.status = "queued"
            job.available_at = datetime.now(UTC) + timedelta(seconds=2**job.attempt)
        else:
            job.status = "failed"
            document.status = "failed"
            job.finished_at = datetime.now(UTC)
        return False
    job.status = "succeeded"
    job.error_message = None
    job.finished_at = datetime.now(UTC)
    return True


async def process_next(database: Database, provider: EmbeddingProvider, settings: Settings) -> bool:
    async with database.sessions() as db:
        job = await db.scalar(
            select(IngestionJob)
            .where(
                IngestionJob.status == "queued",
                IngestionJob.available_at <= datetime.now(UTC),
            )
            .order_by(IngestionJob.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if job is None:
            await db.rollback()
            return False
        await run_job(db, job, provider, settings, persist_progress=True)
        await db.commit()
        return True


async def main() -> None:
    settings = get_settings()
    database = Database(settings)
    provider = FastEmbedProvider(settings.embedding_model, settings.embedding_dimensions)
    try:
        while True:
            worked = await process_next(database, provider, settings)
            if not worked:
                await asyncio.sleep(settings.worker_poll_seconds)
    finally:
        await database.close()


if __name__ == "__main__":
    asyncio.run(main())
