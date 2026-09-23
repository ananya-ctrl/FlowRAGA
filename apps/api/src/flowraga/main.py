import asyncio
import time
from contextlib import asynccontextmanager, suppress
from uuid import uuid4

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from flowraga.api.routes.auth import router as auth_router
from flowraga.api.routes.conversations import router as conversations_router
from flowraga.api.routes.documents import router as documents_router
from flowraga.api.routes.evaluations import router as evaluations_router
from flowraga.api.routes.health import router as health_router
from flowraga.api.routes.pipelines import router as pipelines_router
from flowraga.api.routes.projects import router as projects_router
from flowraga.api.routes.qa import router as qa_router
from flowraga.core.config import get_settings
from flowraga.core.database import Database
from flowraga.core.observability import configure_logging, observe_request
from flowraga.models.dependencies import get_embedding_provider, get_generation_provider
from flowraga.workers.evaluation import process_next as process_evaluation
from flowraga.workers.ingestion import process_next as process_ingestion

settings = get_settings()
configure_logging(settings.log_level)
logger = structlog.get_logger("flowraga.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.database = Database(settings)
    worker_tasks = []
    if settings.run_embedded_workers:

        async def ingestion_loop() -> None:
            provider = get_embedding_provider()
            while True:
                if not await process_ingestion(app.state.database, provider, settings):
                    await asyncio.sleep(settings.worker_poll_seconds)

        async def evaluation_loop() -> None:
            embeddings = get_embedding_provider()
            generation = get_generation_provider()
            while True:
                if not await process_evaluation(
                    app.state.database, settings, embeddings, generation
                ):
                    await asyncio.sleep(settings.worker_poll_seconds)

        worker_tasks = [
            asyncio.create_task(ingestion_loop()),
            asyncio.create_task(evaluation_loop()),
        ]
    yield
    for task in worker_tasks:
        task.cancel()
    for task in worker_tasks:
        with suppress(asyncio.CancelledError):
            await task
    await app.state.database.close()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-CSRF-Token"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    started = time.perf_counter()
    response = await call_next(request)
    route = getattr(request.scope.get("route"), "path", "unmatched")
    observe_request(request.method, route, response.status_code, started)
    logger.info(
        "request_complete",
        request_id=request_id,
        method=request.method,
        route=route,
        status=response.status_code,
        duration_ms=round((time.perf_counter() - started) * 1000, 2),
    )
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


@app.exception_handler(Exception)
async def unexpected_error(_: Request, __: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"code": "internal_error", "message": "An unexpected error occurred"},
    )


app.include_router(health_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(projects_router, prefix="/api/v1")
app.include_router(documents_router, prefix="/api/v1")
app.include_router(qa_router, prefix="/api/v1")
app.include_router(conversations_router, prefix="/api/v1")
app.include_router(evaluations_router, prefix="/api/v1")
app.include_router(pipelines_router, prefix="/api/v1")


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {"name": settings.app_name, "version": settings.app_version}
