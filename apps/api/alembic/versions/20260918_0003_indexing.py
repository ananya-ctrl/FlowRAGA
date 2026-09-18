"""Add vector chunks and retryable ingestion jobs."""

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

revision = "20260918_0003"
down_revision = "20260918_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column(
        "documents",
        sa.Column("indexing_progress", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "documents", sa.Column("chunk_count", sa.Integer(), server_default="0", nullable=False)
    )
    op.create_unique_constraint(
        "uq_documents_project_sha256", "documents", ["project_id", "sha256"]
    )
    op.create_table(
        "document_chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("embedding", Vector(384), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "position", name="uq_chunks_document_position"),
    )
    op.create_index("ix_chunks_project_document", "document_chunks", ["project_id", "document_id"])
    op.execute(
        "CREATE INDEX ix_chunks_embedding_hnsw ON document_chunks "
        "USING hnsw (embedding vector_cosine_ops)"
    )
    op.create_table(
        "ingestion_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("total_chunks", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("available_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ingestion_jobs_document_id", "ingestion_jobs", ["document_id"])
    op.create_index("ix_jobs_status_available", "ingestion_jobs", ["status", "available_at"])


def downgrade() -> None:
    op.drop_table("ingestion_jobs")
    op.execute("DROP INDEX IF EXISTS ix_chunks_embedding_hnsw")
    op.drop_table("document_chunks")
    op.drop_constraint("uq_documents_project_sha256", "documents", type_="unique")
    op.drop_column("documents", "chunk_count")
    op.drop_column("documents", "indexing_progress")
