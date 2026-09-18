import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flowraga.core.config import Settings
from flowraga.db.base import Base
from flowraga.db.models import Document, DocumentChunk, IngestionJob, Project, User
from flowraga.models.embeddings import DeterministicEmbeddingProvider
from flowraga.services.indexing import chunk_text
from flowraga.workers.ingestion import run_job


def test_chunking_is_deterministic_and_overlapping() -> None:
    text = " ".join(f"word-{number}" for number in range(12))
    chunks = chunk_text(text, size=5, overlap=2)
    assert [chunk.token_count for chunk in chunks] == [5, 5, 5, 3]
    assert chunks[0].content.split()[-2:] == chunks[1].content.split()[:2]
    assert chunks == chunk_text(text, size=5, overlap=2)


@pytest.mark.asyncio
async def test_worker_indexes_document_with_vectors(tmp_path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'indexing.db'}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with sessions() as db, db.begin():
        user = User(
            email="worker@example.com",
            display_name="Worker",
            password_hash="not-used-in-this-test",
        )
        db.add(user)
        await db.flush()
        project = Project(owner_id=user.id, name="Indexing")
        db.add(project)
        await db.flush()
        document = Document(
            project_id=project.id,
            owner_id=user.id,
            original_filename="knowledge.txt",
            storage_key=f"{uuid.uuid4().hex}.txt",
            media_type="text/plain",
            size_bytes=100,
            sha256="a" * 64,
            status="queued",
            extracted_text=" ".join(f"fact-{number}" for number in range(140)),
        )
        db.add(document)
        await db.flush()
        job = IngestionJob(
            document_id=document.id,
            project_id=project.id,
            owner_id=user.id,
            max_attempts=3,
        )
        db.add(job)
        await db.flush()
        settings = Settings(
            environment="test",
            database_url="sqlite+aiosqlite://",
            chunk_size_words=50,
            chunk_overlap_words=10,
            embedding_batch_size=2,
        )
        completed = await run_job(
            db, job, DeterministicEmbeddingProvider(settings.embedding_dimensions), settings
        )
        assert completed is True
        assert job.status == "succeeded"
        assert document.status == "ready"
        assert document.indexing_progress == 100
        count = await db.scalar(
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.document_id == document.id)
        )
        assert count == document.chunk_count == 4
        first = await db.scalar(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document.id)
            .order_by(DocumentChunk.position)
        )
        assert first is not None
        assert len(first.embedding) == 384
    await engine.dispose()
