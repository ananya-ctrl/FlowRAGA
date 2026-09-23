# FlowRAGA

FlowRAGA is an open-source visual workspace for building, testing, and evaluating Retrieval-Augmented Generation pipelines.

This repository is an original implementation created independently by Ananya. It is not a fork of the existing FlowRAG or RAGFlow projects.

## Foundation

- **Web:** Next.js, React, TypeScript
- **API:** FastAPI, Pydantic, SQLAlchemy
- **Database:** PostgreSQL with pgvector
- **AI:** local embeddings/reranking plus Ollama or Groq-hosted open-weight generation
- **Storage:** local development storage or private S3-compatible object storage (Cloudflare R2)
- **Infrastructure:** Docker Compose and GitHub Actions

## Local development

1. Copy `.env.example` to `.env` and replace the development database password.
2. Run `docker compose up --build`.
3. Open `http://localhost:3000` for the web app and `http://localhost:8000/docs` for API documentation.

The worker downloads the open-weight `BAAI/bge-small-en-v1.5` model on first use and caches it in a Docker volume. No paid-model dependency or API key is required.

## Hosted production providers

For a Render deployment, set `GENERATION_PROVIDER=groq` with `GROQ_API_KEY` to use
Groq's hosted open-weight Llama model. Set `STORAGE_BACKEND=s3` and the `S3_*`
variables to persist uploads in a private Cloudflare R2 or other S3-compatible
bucket. Secrets belong in the Render environment, never in this repository.

## Repository layout

```text
apps/web     Next.js frontend
apps/api     FastAPI backend
docs         Architecture and engineering decisions
```

## Status

The application now includes secure authentication, protected ingestion, asynchronous indexing, hybrid retrieval, local reranking, grounded answers, persistent conversations, evaluation experiments, a drag-and-drop DAG pipeline editor, saved and active versioned pipelines, portable pipeline JSON, downloadable reports, structured logs, and metrics.

Pipeline graphs validate stage ordering, required nodes, connections, duplicate stages, and cycles before saving. Active chunking, retrieval, reranking, and generation settings are used by ingestion and Q&A execution. See [release readiness](docs/release-readiness.md) before a public deployment.

## License

MIT
