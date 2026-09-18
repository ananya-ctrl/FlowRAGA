import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from flowraga.auth.dependencies import CurrentUser
from flowraga.core.config import get_settings
from flowraga.db.dependencies import DbSession
from flowraga.db.models import Document, Project
from flowraga.schemas.projects import ProjectCreate, ProjectResponse, ProjectUpdate
from flowraga.services.documents import delete_stored_file

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate,
    db: DbSession,
    user: CurrentUser,
) -> Project:
    project = Project(
        owner_id=user.id,
        name=payload.name.strip(),
        description=payload.description,
    )
    db.add(project)
    await db.flush()
    await db.refresh(project)
    return project


@router.get("", response_model=list[ProjectResponse])
async def list_projects(db: DbSession, user: CurrentUser) -> list[Project]:
    projects = await db.scalars(
        select(Project).where(Project.owner_id == user.id).order_by(Project.updated_at.desc())
    )
    return list(projects)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: uuid.UUID, db: DbSession, user: CurrentUser) -> Project:
    project = await db.scalar(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID, payload: ProjectUpdate, db: DbSession, user: CurrentUser
) -> Project:
    project = await get_project(project_id, db, user)
    project.name = payload.name.strip()
    project.description = payload.description
    await db.flush()
    await db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: uuid.UUID, db: DbSession, user: CurrentUser) -> None:
    project = await get_project(project_id, db, user)
    documents = await db.scalars(select(Document).where(Document.project_id == project.id))
    for document in documents:
        delete_stored_file(get_settings(), document.storage_key)
    await db.delete(project)
