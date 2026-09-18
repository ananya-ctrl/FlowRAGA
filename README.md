# FlowRAGA

FlowRAGA is an open-source visual workspace for building, testing, and evaluating Retrieval-Augmented Generation pipelines.

This repository is an original implementation created independently by Ananya. It is not a fork of the existing FlowRAG or RAGFlow projects.

## Foundation

- **Web:** Next.js, React, TypeScript
- **API:** FastAPI, Pydantic, SQLAlchemy
- **Database:** PostgreSQL with pgvector
- **AI:** provider-neutral interfaces for open-weight embedding, reranking, and generation models
- **Infrastructure:** Docker Compose and GitHub Actions

## Local development

1. Copy `.env.example` to `.env` and replace the development database password.
2. Run `docker compose up --build`.
3. Open `http://localhost:3000` for the web app and `http://localhost:8000/docs` for API documentation.

The initial foundation deliberately contains no paid-model dependency and no API keys.

## Repository layout

```text
apps/web     Next.js frontend
apps/api     FastAPI backend
docs         Architecture and engineering decisions
```

## Status

Phase 1 establishes the secure, tested foundation. Authentication, ingestion, RAG execution, evaluation, and visual pipeline capabilities will be added in reviewed phases.

## License

MIT

