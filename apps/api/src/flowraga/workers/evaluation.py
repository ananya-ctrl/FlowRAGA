import asyncio
import time
from datetime import UTC, datetime

from sqlalchemy import delete, select

from flowraga.core.config import Settings, get_settings
from flowraga.core.database import Database
from flowraga.db.models import EvaluationCase, EvaluationResult, EvaluationRun
from flowraga.models.dependencies import get_generation_provider
from flowraga.models.embeddings import FastEmbedProvider
from flowraga.models.generation import GenerationUnavailable
from flowraga.models.providers import EmbeddingProvider, GenerationProvider
from flowraga.services.evaluation import (
    aggregate_metrics,
    citation_metrics,
    retrieval_metrics,
    token_f1,
)
from flowraga.services.retrieval import (
    build_grounded_messages,
    hybrid_retrieve_sources,
    keyword_sources,
    retrieve_sources,
)


async def execute_run(
    db,
    run: EvaluationRun,
    embeddings: EmbeddingProvider,
    generation: GenerationProvider,
    settings: Settings,
    persist_progress: bool = False,
) -> None:
    cases = list(
        await db.scalars(
            select(EvaluationCase)
            .where(EvaluationCase.dataset_id == run.dataset_id)
            .order_by(EvaluationCase.created_at)
        )
    )
    run.status = "running"
    run.started_at = datetime.now(UTC)
    await db.execute(delete(EvaluationResult).where(EvaluationResult.run_id == run.id))
    if persist_progress:
        await db.commit()
    all_metrics = []
    config = run.configuration
    for index, case in enumerate(cases, start=1):
        started = time.perf_counter()
        mode = config.get("retrieval_mode", "hybrid")
        top_k = int(config.get("top_k", 5))
        threshold = float(config.get("similarity_threshold", 0.25))
        if mode == "keyword":
            sources = await keyword_sources(db, run.project_id, run.owner_id, case.question, top_k)
        else:
            query_vector = await embeddings.embed_query(case.question)
            if mode == "vector":
                sources = await retrieve_sources(
                    db, run.project_id, run.owner_id, query_vector, top_k, threshold
                )
            else:
                sources = await hybrid_retrieve_sources(
                    db,
                    run.project_id,
                    run.owner_id,
                    case.question,
                    query_vector,
                    top_k,
                    threshold,
                    settings.hybrid_candidate_multiplier,
                    settings.rrf_constant,
                )
                sources = sources[:top_k]
        retrieval_ms = round((time.perf_counter() - started) * 1000)
        generation_started = time.perf_counter()
        try:
            answer = (
                await generation.generate(
                    build_grounded_messages(
                        case.question, sources, settings.retrieval_max_context_chars
                    )
                )
                if sources
                else "I could not find enough evidence in the indexed documents."
            )
        except GenerationUnavailable:
            answer = "Generation unavailable during evaluation."
        generation_ms = round((time.perf_counter() - generation_started) * 1000)
        source_data = [
            {
                "label": f"S{number}",
                "document_id": str(source.document_id),
                "filename": source.filename,
                "score": round(source.score, 4),
            }
            for number, source in enumerate(sources, start=1)
        ]
        metrics = {
            **retrieval_metrics(
                [str(source.document_id) for source in sources], case.expected_document_ids
            ),
            **citation_metrics(answer, len(sources)),
            "answer_f1": token_f1(answer, case.expected_answer),
            "retrieval_ms": retrieval_ms,
            "generation_ms": generation_ms,
        }
        all_metrics.append(metrics)
        db.add(
            EvaluationResult(
                run_id=run.id,
                case_id=case.id,
                answer=answer,
                sources=source_data,
                metrics=metrics,
                trace={"retrieval_ms": retrieval_ms, "generation_ms": generation_ms, "mode": mode},
            )
        )
        run.progress = round(index / len(cases) * 100)
        await db.flush()
        if persist_progress:
            await db.commit()
    run.summary = aggregate_metrics(all_metrics)
    run.status = "completed"
    run.finished_at = datetime.now(UTC)


async def process_next(database: Database, settings: Settings, embeddings, generation) -> bool:
    async with database.sessions() as db:
        run = await db.scalar(
            select(EvaluationRun)
            .where(EvaluationRun.status == "queued")
            .order_by(EvaluationRun.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if run is None:
            await db.rollback()
            return False
        try:
            await execute_run(db, run, embeddings, generation, settings, True)
        except Exception as exc:
            run.status = "failed"
            run.error_message = (str(exc) or "Evaluation failed")[:500]
            run.finished_at = datetime.now(UTC)
        await db.commit()
        return True


async def main() -> None:
    settings = get_settings()
    database = Database(settings)
    embeddings = FastEmbedProvider(settings.embedding_model, settings.embedding_dimensions)
    generation = get_generation_provider()
    try:
        while True:
            if not await process_next(database, settings, embeddings, generation):
                await asyncio.sleep(settings.worker_poll_seconds)
    finally:
        await database.close()


if __name__ == "__main__":
    asyncio.run(main())
