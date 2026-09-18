"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { createProject, deleteProject, listProjects } from "@/lib/auth-api";

type Project = Awaited<ReturnType<typeof listProjects>>[number];

export default function DashboardPage() {
  const router = useRouter();
  const { user, accessToken, loading, logout } = useAuth();
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectsLoading, setProjectsLoading] = useState(true);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, router, user]);

  useEffect(() => {
    if (!accessToken) return;
    listProjects(accessToken)
      .then(setProjects)
      .finally(() => setProjectsLoading(false));
  }, [accessToken]);

  if (loading || !user) {
    return <main className="center-state">Securing your workspace…</main>;
  }

  return (
    <main className="dashboard-shell">
      <header className="dashboard-nav">
        <Link className="brand" href="/">FlowRAGA</Link>
        <div>
          <span>{user.display_name}</span>
          <button
            className="quiet-button"
            onClick={() => void logout().then(() => router.replace("/login"))}
          >
            Sign out
          </button>
        </div>
      </header>

      <section className="dashboard-heading">
        <p className="eyebrow">Private workspace</p>
        <h1>Your RAG systems, clearly organized.</h1>
        <form className="project-form" onSubmit={(event) => { event.preventDefault(); if (!accessToken) return; setError(""); void createProject(accessToken, {name, description}).then((project) => { setProjects((current) => [project, ...current]); setName(""); setDescription(""); }).catch((reason: Error) => setError(reason.message)); }}>
          <input aria-label="Project name" required maxLength={120} placeholder="Project name" value={name} onChange={(e) => setName(e.target.value)} />
          <input aria-label="Project description" maxLength={2000} placeholder="Short description (optional)" value={description} onChange={(e) => setDescription(e.target.value)} />
          <button className="primary" type="submit">Create project</button>
          {error && <p className="form-error">{error}</p>}
        </form>
      </section>

      <section className="project-list" aria-label="Projects">
        {projectsLoading ? (
          <p className="empty-state">Loading projects…</p>
        ) : projects.length === 0 ? (
          <div className="empty-state">
            <strong>No projects yet.</strong>
            <span>Your first visual RAG workspace will appear here.</span>
          </div>
        ) : (
          projects.map((project) => (
            <article key={project.id}>
              <h2><Link href={`/projects/${project.id}`}>{project.name}</Link></h2>
              <p>{project.description ?? "No description"}</p>
              <button className="quiet-button" onClick={() => { if (!accessToken || !window.confirm(`Delete ${project.name}? Its documents will also be removed.`)) return; void deleteProject(accessToken, project.id).then(() => setProjects((items) => items.filter((item) => item.id !== project.id))); }}>Delete</button>
            </article>
          ))
        )}
      </section>
    </main>
  );
}
