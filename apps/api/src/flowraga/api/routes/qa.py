import time
import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from flowraga.auth.dependencies import CurrentUser
from flowraga.core.config import get_settings
from flowraga.db.dependencies import DbSession
from flowraga.db.models import Project
from flowraga.models.dependencies import EmbeddingDependency, GenerationDependency
from flowraga.models.generation import GenerationUnavailable
from flowraga.schemas.qa import AnswerResponse, QuestionRequest, SourceResponse
from flowraga.services.retrieval import (
    build_grounded_messages,
    ensure_grounded_answer,
    retrieve_sources,
)

router = APIRouter(prefix="/projects/{project_id}/ask", tags=["question answering"])


@router.post("", response_model=AnswerResponse)
async def ask_project(
    project_id: uuid.UUID,
    payload: QuestionRequest,
    db: DbSession,
    user: CurrentUser,
    embeddings: EmbeddingDependency,
    generation: GenerationDependency,
) -> AnswerResponse:
    project = await db.scalar(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    settings = get_settings()
    started = time.perf_counter()
    sources = await retrieve_sources(
        db,
        project_id,
        user.id,
        await embeddings.embed_query(payload.question.strip()),
        payload.top_k or settings.retrieval_default_top_k,
        payload.similarity_threshold
        if payload.similarity_threshold is not None
        else settings.retrieval_default_threshold,
    )
    retrieval_ms = round((time.perf_counter() - started) * 1000)
    source_models = [
        SourceResponse(
            label=f"S{number}",
            chunk_id=source.chunk_id,
            document_id=source.document_id,
            filename=source.filename,
            position=source.position,
            content=source.content,
            score=round(source.score, 4),
        )
        for number, source in enumerate(sources, start=1)
    ]
    if not sources:
        return AnswerResponse(
            answer="I could not find enough evidence in the indexed documents.",
            sources=[],
            retrieval_ms=retrieval_ms,
            generation_ms=None,
            generation_status="skipped_no_evidence",
            model=settings.ollama_model,
        )
    generation_started = time.perf_counter()
    try:
        raw_answer = await generation.generate(
            build_grounded_messages(
                payload.question.strip(), sources, settings.retrieval_max_context_chars
            )
        )
        answer = ensure_grounded_answer(raw_answer, len(sources))
        generation_status = "completed"
    except GenerationUnavailable:
        answer = "Relevant evidence was retrieved, but the local answer model is unavailable."
        generation_status = "unavailable"
    return AnswerResponse(
        answer=answer,
        sources=source_models,
        retrieval_ms=retrieval_ms,
        generation_ms=round((time.perf_counter() - generation_started) * 1000),
        generation_status=generation_status,
        model=settings.ollama_model,
    )
