from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel

from flowraga.core.config import Settings, get_settings

router = APIRouter(prefix="/health", tags=["health"])


class HealthResponse(BaseModel):
    status: str
    version: str


@router.get("/live", response_model=HealthResponse)
async def live(settings: Annotated[Settings, Depends(get_settings)]) -> HealthResponse:
    return HealthResponse(status="ok", version=settings.app_version)


@router.get("/ready", response_model=HealthResponse, responses={503: {"model": HealthResponse}})
async def ready(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> HealthResponse:
    if not await request.app.state.database.ready():
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unavailable", "version": settings.app_version},
        )
    return HealthResponse(status="ready", version=settings.app_version)


@router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
