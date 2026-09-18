export interface User {
  id: string;
  email: string;
  display_name: string;
  created_at: string;
}

export interface Session {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  csrf_token: string;
  user: User;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
  }
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(body?.detail ?? "Something went wrong", response.status);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...init.headers,
    },
  });
  return parseResponse<T>(response);
}

export async function registerAccount(input: {
  email: string;
  display_name: string;
  password: string;
}): Promise<Session> {
  return request<Session>("/api/v1/auth/register", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function loginAccount(input: {
  email: string;
  password: string;
}): Promise<Session> {
  return request<Session>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function createCsrfToken(): Promise<string> {
  const data = await request<{ csrf_token: string }>("/api/v1/auth/csrf");
  return data.csrf_token;
}

export async function restoreSession(csrfToken: string): Promise<Session> {
  return request<Session>("/api/v1/auth/refresh", {
    method: "POST",
    headers: { "X-CSRF-Token": csrfToken },
  });
}

export async function endSession(csrfToken: string): Promise<void> {
  await request<void>("/api/v1/auth/logout", {
    method: "POST",
    headers: { "X-CSRF-Token": csrfToken },
  });
}

export async function listProjects(accessToken: string): Promise<
  Array<{ id: string; name: string; description: string | null; updated_at: string }>
> {
  return request("/api/v1/projects", {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
}
