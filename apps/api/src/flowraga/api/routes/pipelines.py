import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select, update

from flowraga.auth.dependencies import CurrentUser
from flowraga.db.dependencies import DbSession
from flowraga.db.models import Pipeline, Project
from flowraga.schemas.pipelines import (
    PipelineCreate,
    PipelineImport,
    PipelineResponse,
    PipelineUpdate,
)

router = APIRouter(prefix="/projects/{project_id}/pipelines", tags=["pipelines"])


async def owned_project(project_id: uuid.UUID, db: DbSession, user: CurrentUser) -> Project:
    project = await db.scalar(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


async def owned_pipeline(
    project_id: uuid.UUID, pipeline_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> Pipeline:
    pipeline = await db.scalar(
        select(Pipeline).where(
            Pipeline.id == pipeline_id,
            Pipeline.project_id == project_id,
            Pipeline.owner_id == user.id,
        )
    )
    if pipeline is None:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return pipeline


@router.get("/templates")
async def templates() -> list[dict]:
    return [
        {
            "name": "Balanced",
            "configuration": {
                "retrieval_mode": "hybrid",
                "top_k": 5,
                "similarity_threshold": 0.25,
                "rerank": True,
            },
        },
        {
            "name": "Fast",
            "configuration": {
                "retrieval_mode": "vector",
                "top_k": 3,
                "similarity_threshold": 0.3,
                "rerank": False,
            },
        },
        {
            "name": "High recall",
            "configuration": {
                "retrieval_mode": "hybrid",
                "top_k": 10,
                "similarity_threshold": 0.15,
                "rerank": True,
            },
        },
    ]


@router.get("", response_model=list[PipelineResponse])
async def list_pipelines(project_id: uuid.UUID, db: DbSession, user: CurrentUser) -> list[Pipeline]:
    await owned_project(project_id, db, user)
    return list(
        await db.scalars(
            select(Pipeline)
            .where(Pipeline.project_id == project_id, Pipeline.owner_id == user.id)
            .order_by(Pipeline.updated_at.desc())
        )
    )


@router.post("", response_model=PipelineResponse, status_code=status.HTTP_201_CREATED)
async def create_pipeline(
    project_id: uuid.UUID, payload: PipelineCreate, db: DbSession, user: CurrentUser
) -> Pipeline:
    await owned_project(project_id, db, user)
    pipeline = Pipeline(
        project_id=project_id,
        owner_id=user.id,
        name=payload.name.strip(),
        configuration=payload.configuration.model_dump(),
    )
    db.add(pipeline)
    await db.flush()
    await db.refresh(pipeline)
    return pipeline


@router.put("/{pipeline_id}", response_model=PipelineResponse)
async def update_pipeline(
    project_id: uuid.UUID,
    pipeline_id: uuid.UUID,
    payload: PipelineUpdate,
    db: DbSession,
    user: CurrentUser,
) -> Pipeline:
    pipeline = await owned_pipeline(project_id, pipeline_id, db, user)
    pipeline.name = payload.name.strip()
    pipeline.configuration = payload.configuration.model_dump()
    pipeline.version += 1
    await db.flush()
    await db.refresh(pipeline)
    return pipeline


@router.post("/{pipeline_id}/activate", response_model=PipelineResponse)
async def activate_pipeline(
    project_id: uuid.UUID, pipeline_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> Pipeline:
    pipeline = await owned_pipeline(project_id, pipeline_id, db, user)
    await db.execute(
        update(Pipeline)
        .where(Pipeline.project_id == project_id, Pipeline.owner_id == user.id)
        .values(is_active=False)
    )
    pipeline.is_active = True
    await db.flush()
    await db.refresh(pipeline)
    return pipeline


@router.delete("/{pipeline_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pipeline(
    project_id: uuid.UUID, pipeline_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> None:
    await db.delete(await owned_pipeline(project_id, pipeline_id, db, user))


@router.get("/export/all")
async def export_pipelines(project_id: uuid.UUID, db: DbSession, user: CurrentUser) -> dict:
    items = await list_pipelines(project_id, db, user)
    return {
        "format": "flowraga-pipelines-v1",
        "pipelines": [{"name": item.name, "configuration": item.configuration} for item in items],
    }


@router.post("/import", response_model=list[PipelineResponse])
async def import_pipelines(
    project_id: uuid.UUID, payload: PipelineImport, db: DbSession, user: CurrentUser
) -> list[Pipeline]:
    await owned_project(project_id, db, user)
    existing = set(await db.scalars(select(Pipeline.name).where(Pipeline.project_id == project_id)))
    created = []
    for item in payload.pipelines:
        name = item.name.strip()
        if name in existing:
            continue
        pipeline = Pipeline(
            project_id=project_id,
            owner_id=user.id,
            name=name,
            configuration=item.configuration.model_dump(),
        )
        db.add(pipeline)
        created.append(pipeline)
        existing.add(name)
    await db.flush()
    for pipeline in created:
        await db.refresh(pipeline)
    return created
