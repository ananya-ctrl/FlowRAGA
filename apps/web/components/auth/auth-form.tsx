"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { useAuth } from "./auth-provider";
import { ApiError } from "@/lib/auth-api";

export function AuthForm({ mode }: Readonly<{ mode: "login" | "register" }>) {
  const router = useRouter();
  const { login, register } = useAuth();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setPending(true);
    const data = new FormData(event.currentTarget);
    try {
      const email = String(data.get("email"));
      const password = String(data.get("password"));
      if (mode === "register") {
        await register(String(data.get("displayName")), email, password);
      } else {
        await login(email, password);
      }
      router.replace("/dashboard");
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Unable to continue. Please try again.");
    } finally {
      setPending(false);
    }
  }

  const registering = mode === "register";

  return (
    <main className="auth-shell">
      <Link className="auth-brand" href="/">FlowRAGA</Link>
      <section className="auth-card">
        <p className="eyebrow">{registering ? "Create your workspace" : "Welcome back"}</p>
        <h1>{registering ? "Start building transparent RAG." : "Sign in to continue."}</h1>
        <p className="auth-intro">
          {registering
            ? "Your projects and document collections stay isolated under your account."
            : "Return to your pipelines, experiments, and evaluations."}
        </p>

        <form onSubmit={submit}>
          {registering && (
            <label>
              Display name
              <input name="displayName" minLength={2} maxLength={80} autoComplete="name" required />
            </label>
          )}
          <label>
            Email
            <input name="email" type="email" autoComplete="email" required />
          </label>
          <label>
            Password
            <input
              name="password"
              type="password"
              minLength={registering ? 12 : 1}
              maxLength={128}
              autoComplete={registering ? "new-password" : "current-password"}
              required
            />
            {registering && <small>Use at least 12 characters.</small>}
          </label>
          {error && <p className="form-error" role="alert">{error}</p>}
          <button className="primary auth-submit" type="submit" disabled={pending}>
            {pending ? "Please wait…" : registering ? "Create account" : "Sign in"}
          </button>
        </form>

        <p className="auth-switch">
          {registering ? "Already have an account?" : "New to FlowRAGA?"}{" "}
          <Link href={registering ? "/login" : "/signup"}>
            {registering ? "Sign in" : "Create an account"}
          </Link>
        </p>
      </section>
    </main>
  );
}
