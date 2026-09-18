import csv
import io
import uuid

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from flowraga.auth.dependencies import CurrentUser
from flowraga.db.dependencies import DbSession
from flowraga.db.models import Document, EvaluationCase, EvaluationDataset, EvaluationRun, Project
from flowraga.schemas.evaluations import (
    CaseCreate,
    CaseResponse,
    DatasetCreate,
    DatasetResponse,
    RunCreate,
    RunDetail,
    RunResponse,
)

router = APIRouter(prefix="/projects/{project_id}/evaluations", tags=["evaluations"])


async def owned_dataset(project_id, dataset_id, owner_id, db) -> EvaluationDataset:
    dataset = await db.scalar(
        select(EvaluationDataset).where(
            EvaluationDataset.id == dataset_id,
            EvaluationDataset.project_id == project_id,
            EvaluationDataset.owner_id == owner_id,
        )
    )
    if dataset is None:
        raise HTTPException(status_code=404, detail="Evaluation dataset not found")
    return dataset


@router.post("/datasets", response_model=DatasetResponse, status_code=201)
async def create_dataset(
    project_id: uuid.UUID, payload: DatasetCreate, db: DbSession, user: CurrentUser
) -> EvaluationDataset:
    project = await db.scalar(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    dataset = EvaluationDataset(
        project_id=project_id,
        owner_id=user.id,
        name=payload.name.strip(),
        description=payload.description,
    )
    db.add(dataset)
    await db.flush()
    await db.refresh(dataset)
    return dataset


@router.get("/datasets", response_model=list[DatasetResponse])
async def list_datasets(
    project_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> list[EvaluationDataset]:
    items = await db.scalars(
        select(EvaluationDataset)
        .where(EvaluationDataset.project_id == project_id, EvaluationDataset.owner_id == user.id)
        .order_by(EvaluationDataset.created_at.desc())
    )
    return list(items)


@router.post("/datasets/{dataset_id}/cases", response_model=CaseResponse, status_code=201)
async def add_case(
    project_id: uuid.UUID,
    dataset_id: uuid.UUID,
    payload: CaseCreate,
    db: DbSession,
    user: CurrentUser,
) -> EvaluationCase:
    await owned_dataset(project_id, dataset_id, user.id, db)
    expected_ids = {str(item) for item in payload.expected_document_ids}
    if expected_ids:
        valid_ids = {
            str(item)
            for item in await db.scalars(
                select(Document.id).where(
                    Document.project_id == project_id,
                    Document.owner_id == user.id,
                    Document.id.in_(payload.expected_document_ids),
                )
            )
        }
        if valid_ids != expected_ids:
            raise HTTPException(
                status_code=422, detail="A relevant document is not in this project"
            )
    case = EvaluationCase(
        dataset_id=dataset_id,
        owner_id=user.id,
        question=payload.question.strip(),
        expected_answer=payload.expected_answer,
        expected_document_ids=sorted(expected_ids),
    )
    db.add(case)
    await db.flush()
    await db.refresh(case)
    return case


@router.get("/datasets/{dataset_id}/cases", response_model=list[CaseResponse])
async def list_cases(
    project_id: uuid.UUID, dataset_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> list[EvaluationCase]:
    await owned_dataset(project_id, dataset_id, user.id, db)
    items = await db.scalars(
        select(EvaluationCase)
        .where(EvaluationCase.dataset_id == dataset_id, EvaluationCase.owner_id == user.id)
        .order_by(EvaluationCase.created_at)
    )
    return list(items)


@router.post("/datasets/{dataset_id}/runs", response_model=RunResponse, status_code=201)
async def create_run(
    project_id: uuid.UUID,
    dataset_id: uuid.UUID,
    payload: RunCreate,
    db: DbSession,
    user: CurrentUser,
) -> EvaluationRun:
    await owned_dataset(project_id, dataset_id, user.id, db)
    case_count = await db.scalar(
        select(EvaluationCase.id).where(EvaluationCase.dataset_id == dataset_id).limit(1)
    )
    if case_count is None:
        raise HTTPException(status_code=422, detail="Add at least one evaluation case")
    run = EvaluationRun(
        dataset_id=dataset_id,
        project_id=project_id,
        owner_id=user.id,
        configuration=payload.model_dump(),
    )
    db.add(run)
    await db.flush()
    await db.refresh(run)
    return run


@router.get("/datasets/{dataset_id}/runs", response_model=list[RunResponse])
async def list_runs(
    project_id: uuid.UUID, dataset_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> list[EvaluationRun]:
    await owned_dataset(project_id, dataset_id, user.id, db)
    items = await db.scalars(
        select(EvaluationRun)
        .where(EvaluationRun.dataset_id == dataset_id, EvaluationRun.owner_id == user.id)
        .order_by(EvaluationRun.created_at.desc())
    )
    return list(items)


@router.get("/runs/{run_id}", response_model=RunDetail)
async def get_run(
    project_id: uuid.UUID, run_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> EvaluationRun:
    run = await db.scalar(
        select(EvaluationRun)
        .options(selectinload(EvaluationRun.results))
        .where(
            EvaluationRun.id == run_id,
            EvaluationRun.project_id == project_id,
            EvaluationRun.owner_id == user.id,
        )
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Evaluation run not found")
    return run


@router.get("/runs/{run_id}/report")
async def export_report(
    project_id: uuid.UUID, run_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> Response:
    run = await get_run(project_id, run_id, db, user)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "case_id",
            "answer",
            "retrieval_recall",
            "retrieval_precision",
            "citation_validity",
            "citation_coverage",
            "groundedness",
            "answer_f1",
            "retrieval_ms",
            "generation_ms",
        ]
    )
    for result in run.results:
        writer.writerow(
            [
                result.case_id,
                result.answer,
                result.metrics.get("retrieval_recall"),
                result.metrics.get("retrieval_precision"),
                result.metrics.get("citation_validity"),
                result.metrics.get("citation_coverage"),
                result.metrics.get("groundedness"),
                result.metrics.get("answer_f1"),
                result.metrics.get("retrieval_ms"),
                result.metrics.get("generation_ms"),
            ]
        )
    return Response(
        output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="evaluation-{run.id}.csv"'},
    )


@router.post("/runs/{run_id}/retry", response_model=RunResponse)
async def retry_run(
    project_id: uuid.UUID, run_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> EvaluationRun:
    run = await db.scalar(
        select(EvaluationRun).where(
            EvaluationRun.id == run_id,
            EvaluationRun.project_id == project_id,
            EvaluationRun.owner_id == user.id,
        )
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Evaluation run not found")
    if run.status not in {"failed", "completed"}:
        raise HTTPException(status_code=409, detail="Evaluation run is already active")
    run.status = "queued"
    run.progress = 0
    run.summary = None
    run.error_message = None
    run.started_at = None
    run.finished_at = None
    await db.flush()
    await db.refresh(run)
    return run


@router.delete("/datasets/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dataset(
    project_id: uuid.UUID, dataset_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> None:
    dataset = await owned_dataset(project_id, dataset_id, user.id, db)
    await db.delete(dataset)
