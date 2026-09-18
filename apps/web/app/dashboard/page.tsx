"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { listProjects } from "@/lib/auth-api";

type Project = Awaited<ReturnType<typeof listProjects>>[number];

export default function DashboardPage() {
  const router = useRouter();
  const { user, accessToken, loading, logout } = useAuth();
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectsLoading, setProjectsLoading] = useState(true);

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
        <button className="primary" disabled title="Project creation interface is the next phase">
          New project · soon
        </button>
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
              <h2>{project.name}</h2>
              <p>{project.description ?? "No description"}</p>
            </article>
          ))
        )}
      </section>
    </main>
  );
}
