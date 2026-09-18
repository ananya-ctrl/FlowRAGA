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
  const headers = { ...(init.headers as Record<string, string> | undefined) };
  if (init.body && !(init.body instanceof FormData)) headers["Content-Type"] = "application/json";
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    credentials: "include",
    headers,
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

export interface Project { id: string; name: string; description: string | null; updated_at: string; }
export interface UploadedDocument { id: string; project_id: string; original_filename: string; media_type: string; size_bytes: number; sha256: string; status: string; indexing_progress: number; chunk_count: number; error_message: string | null; created_at: string; }
export function createProject(accessToken: string, input: {name: string; description?: string}) { return request<Project>("/api/v1/projects", {method: "POST", headers: {Authorization: `Bearer ${accessToken}`}, body: JSON.stringify(input)}); }
export function getProject(accessToken: string, id: string) { return request<Project>(`/api/v1/projects/${id}`, {headers: {Authorization: `Bearer ${accessToken}`}}); }
export function updateProject(accessToken: string, id: string, input: {name: string; description?: string}) { return request<Project>(`/api/v1/projects/${id}`, {method: "PUT", headers: {Authorization: `Bearer ${accessToken}`}, body: JSON.stringify(input)}); }
export function deleteProject(accessToken: string, id: string) { return request<void>(`/api/v1/projects/${id}`, {method: "DELETE", headers: {Authorization: `Bearer ${accessToken}`}}); }
export function listDocuments(accessToken: string, projectId: string) { return request<UploadedDocument[]>(`/api/v1/projects/${projectId}/documents`, {headers: {Authorization: `Bearer ${accessToken}`}}); }
export function uploadDocument(accessToken: string, projectId: string, file: File) { const body = new FormData(); body.append("file", file); return request<UploadedDocument>(`/api/v1/projects/${projectId}/documents`, {method: "POST", headers: {Authorization: `Bearer ${accessToken}`}, body}); }
export function deleteDocument(accessToken: string, projectId: string, documentId: string) { return request<void>(`/api/v1/projects/${projectId}/documents/${documentId}`, {method: "DELETE", headers: {Authorization: `Bearer ${accessToken}`}}); }
export function retryDocument(accessToken: string, projectId: string, documentId: string) { return request(`/api/v1/projects/${projectId}/documents/${documentId}/retry`, {method: "POST", headers: {Authorization: `Bearer ${accessToken}`}}); }

export interface AnswerSource { label: string; chunk_id: string; document_id: string; filename: string; position: number; content: string; score: number; vector_rank: number | null; keyword_rank: number | null; rerank_score: number | null; }
export interface AnswerResult { conversation_id: string; message_id: string; answer: string; sources: AnswerSource[]; retrieval_ms: number; generation_ms: number | null; generation_status: string; model: string; trace: Record<string, unknown>; }
export interface Conversation { id: string; project_id: string; title: string; created_at: string; updated_at: string; }
export interface ChatMessage { id: string; role: "user" | "assistant"; content: string; sources: AnswerSource[] | null; trace: Record<string, unknown> | null; created_at: string; }
export interface ConversationDetail extends Conversation { messages: ChatMessage[]; }
export interface AskOptions { topK: number; similarityThreshold: number; retrievalMode: "hybrid" | "vector" | "keyword"; rerank: boolean; conversationId?: string; }
export function askProject(accessToken: string, projectId: string, question: string, options: AskOptions = {topK: 5, similarityThreshold: 0.25, retrievalMode: "hybrid", rerank: true}) { return request<AnswerResult>(`/api/v1/projects/${projectId}/ask`, {method: "POST", headers: {Authorization: `Bearer ${accessToken}`}, body: JSON.stringify({question, top_k: options.topK, similarity_threshold: options.similarityThreshold, retrieval_mode: options.retrievalMode, rerank: options.rerank, conversation_id: options.conversationId})}); }
export function listConversations(accessToken: string, projectId: string) { return request<Conversation[]>(`/api/v1/projects/${projectId}/conversations`, {headers: {Authorization: `Bearer ${accessToken}`}}); }
export function getConversation(accessToken: string, projectId: string, conversationId: string) { return request<ConversationDetail>(`/api/v1/projects/${projectId}/conversations/${conversationId}`, {headers: {Authorization: `Bearer ${accessToken}`}}); }
export function deleteConversation(accessToken: string, projectId: string, conversationId: string) { return request<void>(`/api/v1/projects/${projectId}/conversations/${conversationId}`, {method: "DELETE", headers: {Authorization: `Bearer ${accessToken}`}}); }
export function saveAnswerFeedback(accessToken: string, projectId: string, conversationId: string, messageId: string, rating: -1 | 1) { return request(`/api/v1/projects/${projectId}/conversations/${conversationId}/messages/${messageId}/feedback`, {method: "PUT", headers: {Authorization: `Bearer ${accessToken}`}, body: JSON.stringify({rating})}); }
export async function exportConversation(accessToken: string, projectId: string, conversationId: string) { const response = await fetch(`${API_URL}/api/v1/projects/${projectId}/conversations/${conversationId}/export`, {credentials: "include", headers: {Authorization: `Bearer ${accessToken}`}}); if (!response.ok) throw new ApiError("Unable to export conversation", response.status); return response.blob(); }

export interface EvaluationDataset { id: string; project_id: string; name: string; description: string | null; created_at: string; }
export interface EvaluationRun { id: string; dataset_id: string; status: string; configuration: Record<string, unknown>; summary: Record<string, number | null> | null; progress: number; error_message: string | null; created_at: string; }
export function createEvaluationDataset(accessToken: string, projectId: string, input: {name: string; description?: string}) { return request<EvaluationDataset>(`/api/v1/projects/${projectId}/evaluations/datasets`, {method: "POST", headers: {Authorization: `Bearer ${accessToken}`}, body: JSON.stringify(input)}); }
export function listEvaluationDatasets(accessToken: string, projectId: string) { return request<EvaluationDataset[]>(`/api/v1/projects/${projectId}/evaluations/datasets`, {headers: {Authorization: `Bearer ${accessToken}`}}); }
export function addEvaluationCase(accessToken: string, projectId: string, datasetId: string, input: {question: string; expected_answer?: string; expected_document_ids: string[]}) { return request(`/api/v1/projects/${projectId}/evaluations/datasets/${datasetId}/cases`, {method: "POST", headers: {Authorization: `Bearer ${accessToken}`}, body: JSON.stringify(input)}); }
export function createEvaluationRun(accessToken: string, projectId: string, datasetId: string) { return request<EvaluationRun>(`/api/v1/projects/${projectId}/evaluations/datasets/${datasetId}/runs`, {method: "POST", headers: {Authorization: `Bearer ${accessToken}`}, body: JSON.stringify({retrieval_mode: "hybrid", top_k: 5, similarity_threshold: 0.25})}); }
export function listEvaluationRuns(accessToken: string, projectId: string, datasetId: string) { return request<EvaluationRun[]>(`/api/v1/projects/${projectId}/evaluations/datasets/${datasetId}/runs`, {headers: {Authorization: `Bearer ${accessToken}`}}); }
export async function exportEvaluationReport(accessToken: string, projectId: string, runId: string) { const response = await fetch(`${API_URL}/api/v1/projects/${projectId}/evaluations/runs/${runId}/report`, {credentials: "include", headers: {Authorization: `Bearer ${accessToken}`}}); if (!response.ok) throw new ApiError("Unable to export report", response.status); return response.blob(); }

export interface PipelineConfiguration { retrieval_mode: "hybrid" | "vector" | "keyword"; top_k: number; similarity_threshold: number; rerank: boolean; }
export interface Pipeline { id: string; project_id: string; name: string; version: number; is_active: boolean; configuration: PipelineConfiguration; updated_at: string; }
export function listPipelines(accessToken: string, projectId: string) { return request<Pipeline[]>(`/api/v1/projects/${projectId}/pipelines`, {headers: {Authorization: `Bearer ${accessToken}`}}); }
export function createPipeline(accessToken: string, projectId: string, input: {name: string; configuration: PipelineConfiguration}) { return request<Pipeline>(`/api/v1/projects/${projectId}/pipelines`, {method: "POST", headers: {Authorization: `Bearer ${accessToken}`}, body: JSON.stringify(input)}); }
export function activatePipeline(accessToken: string, projectId: string, pipelineId: string) { return request<Pipeline>(`/api/v1/projects/${projectId}/pipelines/${pipelineId}/activate`, {method: "POST", headers: {Authorization: `Bearer ${accessToken}`}}); }
export function deletePipeline(accessToken: string, projectId: string, pipelineId: string) { return request<void>(`/api/v1/projects/${projectId}/pipelines/${pipelineId}`, {method: "DELETE", headers: {Authorization: `Bearer ${accessToken}`}}); }
export async function exportPipelines(accessToken: string, projectId: string) { const data = await request<Record<string, unknown>>(`/api/v1/projects/${projectId}/pipelines/export/all`, {headers: {Authorization: `Bearer ${accessToken}`}}); return new Blob([JSON.stringify(data, null, 2)], {type: "application/json"}); }
export function importPipelines(accessToken: string, projectId: string, data: unknown) { return request<Pipeline[]>(`/api/v1/projects/${projectId}/pipelines/import`, {method: "POST", headers: {Authorization: `Bearer ${accessToken}`}, body: JSON.stringify(data)}); }
