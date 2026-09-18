# Architecture

FlowRAGA begins as a modular monolith. This keeps local development and early deployment simple while preserving boundaries that can later move into workers or separate services.

```mermaid
flowchart TD
    Browser[Next.js web application] --> API[FastAPI application]
    API --> Domain[Application services]
    Domain --> Providers[Model provider interfaces]
    Domain --> Database[(PostgreSQL and pgvector)]
    Domain --> Jobs[Background jobs - planned]
```

## Engineering rules

1. Route handlers validate transport data and delegate business logic.
2. Domain services do not depend on FastAPI or browser concerns.
3. Model calls pass through explicit provider interfaces.
4. Credentials are read only from server-side environment variables.
5. User-owned records will always carry an owner identifier before public ingestion endpoints are introduced.
6. Long-running ingestion and evaluation will execute outside API request workers.
7. Open-weight local models are the default; hosted providers are optional adapters.

## Identity and session security

- Passwords are hashed with Argon2.
- Access tokens are short-lived JWTs with issuer, audience, type, expiry, and unique ID claims.
- Refresh tokens are opaque random values; only SHA-256 digests are stored.
- Refresh tokens rotate on every use and can be revoked independently.
- Projects include a non-null owner identifier and queries must filter by that owner.
- Browser refresh tokens are transmitted only through HttpOnly cookies.
- Access tokens and CSRF tokens are held in application memory, not local storage.
- Cookie-backed refresh and logout operations require a matching CSRF cookie and header.
- The browser obtains a short-lived CSRF token before attempting session restoration.

## Document ingestion security

- Documents are isolated by both project and owner identifiers.
- Uploads stream to generated storage keys and never use user-provided filenames as paths.
- PDF and DOCX signatures are verified; text inputs must be UTF-8 and non-binary.
- DOCX archives are checked for traversal, encryption, excessive entries, expansion, and compression ratios before parsing.
- File size, PDF page count, and archive expansion limits are configurable.
- Local storage is the initial adapter; object storage and asynchronous extraction can replace it without changing the API contract.

## Planned model defaults

- Embeddings: `BAAI/bge-small-en-v1.5`
- Multilingual embeddings: `BAAI/bge-m3`
- Reranking: `BAAI/bge-reranker-base`
- Generation: provider adapter supporting local Ollama-compatible open-weight models

Model packages are intentionally not installed in the foundation image. They will be introduced with resource limits, caching, health checks, and benchmarks during the RAG core phase.
