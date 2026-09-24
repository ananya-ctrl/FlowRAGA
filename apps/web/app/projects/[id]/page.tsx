"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { FormEvent, useEffect, useMemo, useState } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { AppShell } from "@/components/app-shell";
import { ProjectChat } from "@/components/project-chat";
import { EvaluationPanel } from "@/components/evaluation-panel";
import { PipelinePanel } from "@/components/pipeline-panel";
import {
  deleteDocument,
  getProject,
  listDocuments,
  Project,
  retryDocument,
  UploadedDocument,
  uploadDocument,
} from "@/lib/auth-api";

export default function ProjectPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { accessToken, user, loading, logout } = useAuth();
  const [project, setProject] = useState<Project | null>(null);
  const [documents, setDocuments] = useState<UploadedDocument[]>([]);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, router, user]);

  useEffect(() => {
    if (!accessToken) return;
    Promise.all([getProject(accessToken, id), listDocuments(accessToken, id)])
      .then(([p, docs]) => {
        setProject(p);
        setDocuments(docs);
      })
      .catch((reason: Error) => setError(reason.message));
  }, [accessToken, id]);

  useEffect(() => {
    if (!accessToken || !documents.some((document) => ["queued", "indexing"].includes(document.status))) return;
    const timer = window.setInterval(() => void listDocuments(accessToken, id).then(setDocuments), 2000);
    return () => window.clearInterval(timer);
  }, [accessToken, documents, id]);

  function submitUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const input = event.currentTarget.elements.namedItem("document") as HTMLInputElement;
    const file = input.files?.[0];
    if (!file || !accessToken) return;
    setUploading(true);
    setError("");
    void uploadDocument(accessToken, id, file)
      .then((document) => {
        setDocuments((items) => [document, ...items]);
        input.value = "";
      })
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setUploading(false));
  }

  const stats = useMemo(() => {
    const ready = documents.filter((d) => d.status === "ready");
    const totalChunks = ready.reduce((sum, d) => sum + (d.chunk_count ?? 0), 0);
    return [
      { label: "Documents", value: documents.length, icon: "\ud83d\udcc4", tone: "" },
      { label: "Chunks indexed", value: totalChunks, icon: "\ud83d\uddc3\ufe0f", tone: "purple" },
      { label: "Ready", value: ready.length, icon: "\u2705", tone: "blue" },
    ];
  }, [documents]);

  if (loading || !user || !project || !accessToken) {
    return <main className="center-state">Opening your project\u2026{error && ` ${error}`}</main>;
  }

  return (
    <AppShell
      userName={user.display_name}
      onSignOut={() => void logout().then(() => router.replace("/login"))}
      topbar={
        <>
          <Link className="back-link" href="/dashboard">&larr; All projects</Link>
          <strong>{project.name}</strong>
        </>
      }
    >
      <section className="page-heading">
        <p className="eyebrow">Project workspace</p>
        <h1>{project.name}</h1>
        {project.description && <p>{project.description}</p>}
      </section>

      <div className="stat-grid">
        {stats.map((stat) => (
          <div className={`stat-card ${stat.tone}`} key={stat.label}>
            <span className="stat-icon" aria-hidden="true">{stat.icon}</span>
            <div>
              <div className="stat-label">{stat.label}</div>
              <div className="stat-value">{stat.value}</div>
            </div>
          </div>
        ))}
      </div>

      <PipelinePanel projectId={id} accessToken={accessToken} />
      <ProjectChat projectId={id} accessToken={accessToken} />
      <EvaluationPanel projectId={id} accessToken={accessToken} />

      <section className="document-panel">
        <h2>Knowledge sources</h2>
        <p>Upload PDF, TXT, Markdown, or DOCX. Maximum 25 MB.</p>
        <form onSubmit={submitUpload}>
          <input name="document" type="file" required accept=".pdf,.txt,.md,.docx" />
          <button className="primary" disabled={uploading}>{uploading ? "Validating\u2026" : "Upload document"}</button>
        </form>
        {error && <p className="form-error">{error}</p>}
        <div className="document-list">
          {documents.length === 0 ? (
            <p className="empty-state">No documents yet.</p>
          ) : (
            documents.map((document) => (
              <article key={document.id}>
                <div>
                  <strong>{document.original_filename}</strong>
                  <span>
                    {(document.size_bytes / 1024).toFixed(1)} KB &middot; {document.status}
                    {document.status === "ready" ? ` \u00b7 ${document.chunk_count} chunks` : ` \u00b7 ${document.indexing_progress}%`}
                  </span>
                  {["queued", "indexing"].includes(document.status) && (
                    <progress max="100" value={document.indexing_progress} aria-label={`Indexing ${document.original_filename}`} />
                  )}
                  {document.error_message && <small className="form-error">{document.error_message}</small>}
                </div>
                <div className="document-actions">
                  {document.status === "failed" && (
                    <button
                      className="quiet-button"
                      onClick={() => {
                        void retryDocument(accessToken, id, document.id).then(() =>
                          setDocuments((items) =>
                            items.map((item) =>
                              item.id === document.id
                                ? { ...item, status: "queued", indexing_progress: 0, error_message: null }
                                : item,
                            ),
                          ),
                        );
                      }}
                    >
                      Retry
                    </button>
                  )}
                  <button
                    className="quiet-button"
                    onClick={() => {
                      void deleteDocument(accessToken, id, document.id).then(() =>
                        setDocuments((items) => items.filter((item) => item.id !== document.id)),
                      );
                    }}
                  >
                    Remove
                  </button>
                </div>
              </article>
            ))
          )}
        </div>
      </section>
    </AppShell>
  );
}
