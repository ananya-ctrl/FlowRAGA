"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { useAuth } from "@/components/auth/auth-provider";
import { deleteDocument, getProject, listDocuments, Project, UploadedDocument, uploadDocument } from "@/lib/auth-api";

export default function ProjectPage() {
  const { id } = useParams<{id: string}>(); const router = useRouter();
  const { accessToken, user, loading } = useAuth(); const [project, setProject] = useState<Project | null>(null);
  const [documents, setDocuments] = useState<UploadedDocument[]>([]); const [error, setError] = useState(""); const [uploading, setUploading] = useState(false);
  useEffect(() => { if (!loading && !user) router.replace("/login"); }, [loading, router, user]);
  useEffect(() => { if (!accessToken) return; Promise.all([getProject(accessToken, id), listDocuments(accessToken, id)]).then(([p, docs]) => { setProject(p); setDocuments(docs); }).catch((reason: Error) => setError(reason.message)); }, [accessToken, id]);
  function submitUpload(event: FormEvent<HTMLFormElement>) { event.preventDefault(); const input = event.currentTarget.elements.namedItem("document") as HTMLInputElement; const file = input.files?.[0]; if (!file || !accessToken) return; setUploading(true); setError(""); void uploadDocument(accessToken, id, file).then((document) => { setDocuments((items) => [document, ...items]); input.value = ""; }).catch((reason: Error) => setError(reason.message)).finally(() => setUploading(false)); }
  if (loading || !user || !project) return <main className="center-state">Opening your project…{error && ` ${error}`}</main>;
  return <main className="dashboard-shell"><header className="dashboard-nav"><Link className="brand" href="/dashboard">← FlowRAGA</Link><span>{user.display_name}</span></header><section className="dashboard-heading"><p className="eyebrow">Project workspace</p><h1>{project.name}</h1><p>{project.description}</p></section><section className="document-panel"><h2>Knowledge sources</h2><p>Upload PDF, TXT, Markdown, or DOCX. Maximum 25 MB.</p><form onSubmit={submitUpload}><input name="document" type="file" required accept=".pdf,.txt,.md,.docx" /><button className="primary" disabled={uploading}>{uploading ? "Validating…" : "Upload document"}</button></form>{error && <p className="form-error">{error}</p>}<div className="document-list">{documents.length === 0 ? <p className="empty-state">No documents yet.</p> : documents.map((document) => <article key={document.id}><div><strong>{document.original_filename}</strong><span>{(document.size_bytes / 1024).toFixed(1)} KB · {document.status}</span></div><button className="quiet-button" onClick={() => { if (!accessToken) return; void deleteDocument(accessToken, id, document.id).then(() => setDocuments((items) => items.filter((item) => item.id !== document.id))); }}>Remove</button></article>)}</div></section></main>;
}
