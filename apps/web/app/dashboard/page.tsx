"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { AppShell } from "@/components/app-shell";
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

  const stats = useMemo(
    () => [
      { label: "Projects", value: projects.length, icon: "\ud83d\udcc1", tone: "" },
      { label: "This week", value: "\u2014", icon: "\u2728", tone: "blue" },
      { label: "Active workspace", value: user?.display_name ?? "\u2014", icon: "\ud83d\udc64", tone: "purple" },
    ],
    [projects.length, user],
  );

  if (loading || !user) {
    return <main className="center-state">Securing your workspace\u2026</main>;
  }

  return (
    <AppShell
      userName={user.display_name}
      onSignOut={() => void logout().then(() => router.replace("/login"))}
      topbar={
        <>
          <div>
            <strong>Overview</strong>
          </div>
        </>
      }
    >
      <section className="page-heading">
        <p className="eyebrow">Private workspace</p>
        <h1>Your RAG systems, clearly organized.</h1>
        <p>Create a project, upload source documents, and build a retrieval pipeline for each one.</p>
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

      <section className="panel">
        <h2>New project</h2>
        <p>Give it a name your team will recognize.</p>
        <form
          className="project-form"
          onSubmit={(event) => {
            event.preventDefault();
            if (!accessToken) return;
            setError("");
            void createProject(accessToken, { name, description })
              .then((project) => {
                setProjects((current) => [project, ...current]);
                setName("");
                setDescription("");
              })
              .catch((reason: Error) => setError(reason.message));
          }}
        >
          <input
            aria-label="Project name"
            required
            maxLength={120}
            placeholder="Project name"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <input
            aria-label="Project description"
            maxLength={2000}
            placeholder="Short description (optional)"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
          <button className="primary" type="submit">Create project</button>
        </form>
        {error && <p className="form-error">{error}</p>}
      </section>

      <section className="project-list" aria-label="Projects">
        {projectsLoading ? (
          <p className="empty-state">Loading projects\u2026</p>
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
              <button
                className="quiet-button"
                onClick={() => {
                  if (!accessToken || !window.confirm(`Delete ${project.name}? Its documents will also be removed.`)) return;
                  void deleteProject(accessToken, project.id).then(() =>
                    setProjects((items) => items.filter((item) => item.id !== project.id)),
                  );
                }}
              >
                Delete
              </button>
            </article>
          ))
        )}
      </section>
    </AppShell>
  );
}
