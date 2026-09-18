# Release readiness

FlowRAGA is designed to remain free and self-hosted. PostgreSQL/pgvector, FastEmbed, the reranker, and Ollama are open-source components; no paid model key is required.

## Production checklist

1. Set `ENVIRONMENT=production`, a random `JWT_SECRET` of at least 32 characters, `AUTH_COOKIE_SECURE=true`, and an exact HTTPS `CORS_ORIGINS` list.
2. Use managed PostgreSQL with the pgvector extension and an encrypted `DATABASE_URL` secret.
3. Put uploads and the model cache on persistent storage. Back up PostgreSQL and uploads together.
4. Run the API, ingestion worker, evaluation worker, web application, PostgreSQL, and Ollama as separate services.
5. Route HTTPS traffic to the web and API only. Keep PostgreSQL and Ollama private.
6. Apply migrations before traffic, then verify `/api/v1/health/live`, `/api/v1/health/ready`, and `/api/v1/health/metrics`.
7. Pin container image versions for a production release and monitor request, retrieval, generation, queue, disk, and database health.

## Recovery

- Roll back the application image while keeping database migrations forward-compatible.
- Restore the database and upload storage from the same backup point.
- Re-index documents if the embedding model changes.
- Export pipeline JSON before major configuration changes; imports reject invalid or oversized settings.
