# Security policy

Please report vulnerabilities privately to the repository owner instead of opening a public issue. Do not include credentials or private documents in reports.

Supported security controls include owner-scoped database access, Argon2 password hashing, rotating refresh sessions, CSRF protection, strict CORS, bounded uploads, archive validation, secure production-cookie enforcement, non-root containers, structured content-safe logging, and local model execution.

Before public deployment, follow `docs/release-readiness.md` and rotate any credential that may have appeared in logs or development files.
