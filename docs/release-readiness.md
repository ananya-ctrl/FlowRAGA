# Release readiness

FlowRAGA uses PostgreSQL/pgvector, FastEmbed, and an open-weight generation model.
Local deployments can use Ollama. Hosted deployments can use Groq's free allowance
for Llama generation and Cloudflare R2's included allowance for durable uploads.
Provider free-plan limits and availability are controlled by those providers.

## Production checklist

1. Set `ENVIRONMENT=production`, a random `JWT_SECRET` of at least 32 characters, `AUTH_COOKIE_SECURE=true`, and an exact HTTPS `CORS_ORIGINS` list.
2. Use managed PostgreSQL with the pgvector extension and an encrypted `DATABASE_URL` secret.
3. Set `STORAGE_BACKEND=s3` and configure a private S3-compatible bucket. Back up PostgreSQL and uploads together.
4. Run the API, ingestion worker, evaluation worker, web application, PostgreSQL, and Ollama as separate services.
5. Route HTTPS traffic to the web and API only. Keep PostgreSQL and Ollama private.
6. Apply migrations before traffic, then verify `/api/v1/health/live`, `/api/v1/health/ready`, and `/api/v1/health/metrics`.
7. Pin container image versions for a production release and monitor request, retrieval, generation, queue, disk, and database health.
8. Set `GENERATION_PROVIDER=groq`, `GROQ_API_KEY`, and an active `GROQ_MODEL`. Never expose either provider's credentials to the browser.

## Required hosted environment variables

- `GENERATION_PROVIDER=groq`
- `GROQ_API_KEY` and `GROQ_MODEL=llama-3.3-70b-versatile`
- `STORAGE_BACKEND=s3`
- `S3_BUCKET`, `S3_ENDPOINT_URL`, `S3_REGION=auto`
- `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, and optionally `S3_KEY_PREFIX`

The bucket must remain private. The API performs server-side uploads and deletes,
so browser CORS or public bucket access is unnecessary.

For a constrained single-service demo, `RUN_EMBEDDED_WORKERS=true` runs ingestion and evaluation loops inside the API process. Production deployments should use independent workers. Cross-origin HTTPS deployments automatically use `SameSite=None` secure session cookies.

## Recovery

- Roll back the application image while keeping database migrations forward-compatible.
- Restore the database and upload storage from the same backup point.
- Re-index documents if the embedding model changes.
- Export pipeline JSON before major configuration changes; imports reject invalid or oversized settings.
