import uuid
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool

from flowraga.auth.dependencies import CurrentUser
from flowraga.core.config import get_settings
from flowraga.db.dependencies import DbSession
from flowraga.db.models import Document, IngestionJob, Project
from flowraga.schemas.documents import DocumentResponse, IngestionJobResponse
from flowraga.services.documents import (
    InvalidDocument,
    delete_stored_file,
    store_upload,
    validate_and_extract,
)

router = APIRouter(prefix="/projects/{project_id}/documents", tags=["documents"])


async def owned_project(project_id: uuid.UUID, db: DbSession, user: CurrentUser) -> Project:
    project = await db.scalar(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
    file: Annotated[UploadFile, File()],
) -> Document:
    await owned_project(project_id, db, user)
    settings = get_settings()
    path = None
    try:
        key, path, size, checksum = await store_upload(file, settings)
        media_type, extracted_text = await run_in_threadpool(validate_and_extract, path, settings)
        duplicate = await db.scalar(
            select(Document).where(
                Document.project_id == project_id,
                Document.owner_id == user.id,
                Document.sha256 == checksum,
            )
        )
        if duplicate is not None:
            path.unlink(missing_ok=True)
            raise HTTPException(status_code=409, detail="This document is already in the project")
    except InvalidDocument as exc:
        if path is not None:
            path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        await file.close()
    document = Document(
        project_id=project_id,
        owner_id=user.id,
        original_filename=(file.filename or "document")[:255],
        storage_key=key,
        media_type=media_type,
        size_bytes=size,
        sha256=checksum,
        status="queued",
        extracted_text=extracted_text,
    )
    db.add(document)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=409, detail="This document is already in the project"
        ) from exc
    db.add(
        IngestionJob(
            document_id=document.id,
            project_id=project_id,
            owner_id=user.id,
            max_attempts=settings.ingestion_max_attempts,
        )
    )
    await db.flush()
    await db.refresh(document)
    return document


@router.get("", response_model=list[DocumentResponse])
async def list_documents(project_id: uuid.UUID, db: DbSession, user: CurrentUser) -> list[Document]:
    await owned_project(project_id, db, user)
    documents = await db.scalars(
        select(Document)
        .where(Document.project_id == project_id, Document.owner_id == user.id)
        .order_by(Document.created_at.desc())
    )
    return list(documents)


@router.get("/jobs", response_model=list[IngestionJobResponse])
async def list_ingestion_jobs(
    project_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> list[IngestionJob]:
    await owned_project(project_id, db, user)
    jobs = await db.scalars(
        select(IngestionJob)
        .where(IngestionJob.project_id == project_id, IngestionJob.owner_id == user.id)
        .order_by(IngestionJob.created_at.desc())
    )
    return list(jobs)


@router.post("/{document_id}/retry", response_model=IngestionJobResponse, status_code=201)
async def retry_ingestion(
    project_id: uuid.UUID, document_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> IngestionJob:
    document = await db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.project_id == project_id,
            Document.owner_id == user.id,
        )
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    active = await db.scalar(
        select(IngestionJob).where(
            IngestionJob.document_id == document.id,
            IngestionJob.status.in_(["queued", "running"]),
        )
    )
    if active is not None:
        raise HTTPException(status_code=409, detail="Document is already queued")
    document.status = "queued"
    document.error_message = None
    document.indexing_progress = 0
    job = IngestionJob(
        document_id=document.id,
        project_id=project_id,
        owner_id=user.id,
        max_attempts=get_settings().ingestion_max_attempts,
    )
    db.add(job)
    await db.flush()
    await db.refresh(job)
    return job


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    project_id: uuid.UUID, document_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> None:
    document = await db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.project_id == project_id,
            Document.owner_id == user.id,
        )
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    delete_stored_file(get_settings(), document.storage_key)
    await db.delete(document)
