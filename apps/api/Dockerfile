FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

ARG INSTALL_MODELS=false

RUN addgroup --system flowraga && adduser --system --ingroup flowraga flowraga
RUN mkdir -p /app/data/uploads /app/model-cache && chown -R flowraga:flowraga /app/data /app/model-cache

COPY pyproject.toml ./
COPY alembic.ini ./
COPY alembic ./alembic
COPY src ./src
RUN if [ "$INSTALL_MODELS" = "true" ]; then pip install --no-cache-dir '.[models]'; else pip install --no-cache-dir .; fi

USER flowraga
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/live', timeout=3)"

CMD ["sh", "-c", "alembic upgrade head && uvicorn flowraga.main:app --host 0.0.0.0 --port 8000 --no-server-header"]
