import time
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from flowraga.auth.dependencies import CurrentUser
from flowraga.core.config import get_settings
from flowraga.core.observability import observe_ai_operation
from flowraga.db.dependencies import DbSession
from flowraga.db.models import ChatConversation, ChatMessage, Pipeline, Project
from flowraga.models.dependencies import (
    EmbeddingDependency,
    GenerationDependency,
    RerankingDependency,
)
from flowraga.models.generation import GenerationUnavailable
from flowraga.schemas.qa import AnswerResponse, QuestionRequest, SourceResponse
from flowraga.services.retrieval import (
    build_grounded_messages,
    ensure_grounded_answer,
    hybrid_retrieve_sources,
    keyword_sources,
    retrieve_sources,
)

router = APIRouter(prefix="/projects/{project_id}/ask", tags=["question answering"])


async def resolve_conversation(
    db, project_id: uuid.UUID, owner_id: uuid.UUID, payload: QuestionRequest
) -> ChatConversation:
    if payload.conversation_id is not None:
        conversation = await db.scalar(
            select(ChatConversation).where(
                ChatConversation.id == payload.conversation_id,
                ChatConversation.project_id == project_id,
                ChatConversation.owner_id == owner_id,
            )
        )
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return conversation
    conversation = ChatConversation(
        project_id=project_id,
        owner_id=owner_id,
        title=payload.question.strip()[:160],
    )
    db.add(conversation)
    await db.flush()
    return conversation


@router.post("", response_model=AnswerResponse)
async def ask_project(
    project_id: uuid.UUID,
    payload: QuestionRequest,
    db: DbSession,
    user: CurrentUser,
    embeddings: EmbeddingDependency,
    generation: GenerationDependency,
    reranker: RerankingDependency,
) -> AnswerResponse:
    project = await db.scalar(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    conversation = await resolve_conversation(db, project_id, user.id, payload)
    question = payload.question.strip()
    user_message = ChatMessage(
        conversation_id=conversation.id,
        project_id=project_id,
        owner_id=user.id,
        role="user",
        content=question,
        created_at=datetime.now(UTC),
    )
    db.add(user_message)
    settings = get_settings()
    active_pipeline = await db.scalar(
        select(Pipeline).where(
            Pipeline.project_id == project_id,
            Pipeline.owner_id == user.id,
            Pipeline.is_active.is_(True),
        )
    )
    pipeline = active_pipeline.configuration if active_pipeline else {}
    top_k = pipeline.get("top_k") or payload.top_k or settings.retrieval_default_top_k
    threshold = (
        pipeline.get("similarity_threshold")
        if active_pipeline
        else payload.similarity_threshold
        if payload.similarity_threshold is not None
        else settings.retrieval_default_threshold
    )
    retrieval_mode = pipeline.get("retrieval_mode", payload.retrieval_mode)
    rerank_enabled = pipeline.get("rerank", payload.rerank)
    started = time.perf_counter()
    candidate_limit = top_k * settings.hybrid_candidate_multiplier
    if retrieval_mode == "vector":
        query_vector = await embeddings.embed_query(question)
        sources = await retrieve_sources(
            db, project_id, user.id, query_vector, candidate_limit, threshold
        )
    elif retrieval_mode == "keyword":
        sources = await keyword_sources(db, project_id, user.id, question, candidate_limit)
    else:
        query_vector = await embeddings.embed_query(question)
        sources = await hybrid_retrieve_sources(
            db,
            project_id,
            user.id,
            question,
            query_vector,
            top_k,
            threshold,
            settings.hybrid_candidate_multiplier,
            settings.rrf_constant,
        )
    reranker_status = "disabled"
    if rerank_enabled and sources and reranker is not None:
        try:
            ranked = await reranker.rerank(question, [source.content for source in sources])
            sources = [
                source.__class__(**{**source.__dict__, "rerank_score": score})
                for index, score in ranked
                for source in [sources[index]]
            ]
            reranker_status = "completed"
        except Exception:
            reranker_status = "fallback"
    candidate_count = len(sources)
    sources = sources[:top_k]
    retrieval_ms = round((time.perf_counter() - started) * 1000)
    observe_ai_operation("retrieval", "completed", time.perf_counter() - started)
    source_models = [
        SourceResponse(
            label=f"S{number}",
            chunk_id=source.chunk_id,
            document_id=source.document_id,
            filename=source.filename,
            position=source.position,
            content=source.content,
            score=round(source.score, 4),
            vector_rank=source.vector_rank,
            keyword_rank=source.keyword_rank,
            rerank_score=source.rerank_score,
        )
        for number, source in enumerate(sources, start=1)
    ]
    generation_ms = None
    if not sources:
        answer = "I could not find enough evidence in the indexed documents."
        generation_status = "skipped_no_evidence"
    else:
        generation_started = time.perf_counter()
        try:
            raw_answer = await generation.generate(
                build_grounded_messages(question, sources, settings.retrieval_max_context_chars)
            )
            answer = ensure_grounded_answer(raw_answer, len(sources))
            generation_status = "completed"
        except GenerationUnavailable:
            answer = "Relevant evidence was retrieved, but the local answer model is unavailable."
            generation_status = "unavailable"
        generation_ms = round((time.perf_counter() - generation_started) * 1000)
        observe_ai_operation(
            "generation", generation_status, time.perf_counter() - generation_started
        )
    trace = {
        "retrieval_mode": retrieval_mode,
        "pipeline_id": str(active_pipeline.id) if active_pipeline else None,
        "top_k": top_k,
        "similarity_threshold": threshold,
        "candidate_limit": candidate_limit,
        "candidate_count": candidate_count,
        "returned_count": len(sources),
        "reranker_status": reranker_status,
        "retrieval_ms": retrieval_ms,
        "generation_ms": generation_ms,
    }
    assistant_message = ChatMessage(
        conversation_id=conversation.id,
        project_id=project_id,
        owner_id=user.id,
        role="assistant",
        content=answer,
        sources=[source.model_dump(mode="json") for source in source_models],
        trace=trace,
        created_at=datetime.now(UTC),
    )
    db.add(assistant_message)
    conversation.updated_at = datetime.now(UTC)
    await db.flush()
    return AnswerResponse(
        conversation_id=conversation.id,
        message_id=assistant_message.id,
        answer=answer,
        sources=source_models,
        retrieval_ms=retrieval_ms,
        generation_ms=generation_ms,
        generation_status=generation_status,
        model=settings.ollama_model,
        trace=trace,
    )
