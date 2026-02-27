import type {
  ApiKeyItem,
  ApiStateResponse,
  ApiStatusResponse,
  DbStatusResponse,
  DraftResponse,
  PostDetailResponse,
  PostsResponse,
  ProposalsResponse,
  PromptItem,
  ResearchConfig,
  ResearchConfigResponse,
  RunResponse,
  TextProposal,
  SyncMetricsResponse,
} from "../types";
import type { SchedulerState, SchedulerConfig } from "../types/scheduler";

let tokenGetter: (() => string) | null = null;

export function setApiTokenGetter(getter: () => string) {
  tokenGetter = getter;
}

async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers || {});
  if (!headers.has("Content-Type") && init.body) {
    headers.set("Content-Type", "application/json");
  }

  const token = tokenGetter?.().trim() || "";
  if (token && !headers.has("X-API-Token")) {
    headers.set("X-API-Token", token);
  }

  const response = await fetch(path, { ...init, headers });
  const body = await response.json().catch(() => ({}));

  if (!response.ok) {
    const errorMessage =
      (typeof body?.error === "string" && body.error) ||
      (typeof body?.error_summary === "string" && body.error_summary) ||
      `HTTP ${response.status}`;
    const error = new Error(errorMessage) as Error & { status?: number; body?: unknown };
    error.status = response.status;
    error.body = body;
    throw error;
  }

  return body as T;
}

export const apiClient = {
  getState: () => apiFetch<ApiStateResponse>("/api/state"),
  getStatus: () => apiFetch<ApiStatusResponse>("/api/status"),
  runPipeline: (payload: {
    mode: "test" | "dry-run" | "live";
    template?: number;
    topic?: string;
  }) =>
    apiFetch<RunResponse>("/api/run", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  searchTopic: (topic: string) =>
    apiFetch<RunResponse>("/api/search-topic", {
      method: "POST",
      body: JSON.stringify({ topic }),
    }),
  generateProposals: (payload: { topic?: string; count?: number }) =>
    apiFetch<ProposalsResponse>("/api/proposals", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  createDraft: (payload: {
    topic: Record<string, unknown>;
    proposal: TextProposal;
    template?: number;
  }) =>
    apiFetch<DraftResponse>("/api/drafts", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getKeys: () => apiFetch<ApiKeyItem[]>("/api/keys"),
  saveKeys: (payload: Record<string, string>) =>
    apiFetch<{ saved: number }>("/api/keys", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getPrompts: () => apiFetch<PromptItem[]>("/api/prompts"),
  savePrompt: (id: string, text: string) =>
    apiFetch<{ saved: string }>("/api/prompts", {
      method: "POST",
      body: JSON.stringify({ id, text }),
    }),
  resetPrompt: (id: string) =>
    apiFetch<{ reset: string }>("/api/prompts/reset", {
      method: "POST",
      body: JSON.stringify({ id }),
    }),
  getResearchConfig: () => apiFetch<ResearchConfigResponse>("/api/research-config"),
  saveResearchConfig: (config: ResearchConfig) =>
    apiFetch<{ saved: boolean }>("/api/research-config", {
      method: "POST",
      body: JSON.stringify({ config }),
    }),
  resetResearchConfig: () =>
    apiFetch<{ reset: boolean }>("/api/research-config/reset", {
      method: "POST",
      body: JSON.stringify({}),
    }),
  getPosts: (limit = 20) => apiFetch<PostsResponse>(`/api/posts?limit=${limit}`),
  getPostDetail: (postId: number) => apiFetch<PostDetailResponse>(`/api/posts/${postId}`),
  publishPost: (postId: number) =>
    apiFetch<{ media_id?: string; status?: string }>("/api/posts/" + postId + "/publish", {
      method: "POST",
      body: JSON.stringify({}),
    }),
  retryPublish: (postId: number) =>
    apiFetch<{ media_id?: string; status?: string }>("/api/posts/" + postId + "/retry-publish", {
      method: "POST",
      body: JSON.stringify({}),
    }),
  getDbStatus: () => apiFetch<DbStatusResponse>("/api/db-status"),
  syncMetrics: (limit = 30) =>
    apiFetch<SyncMetricsResponse>("/api/posts/sync-metrics", {
      method: "POST",
      body: JSON.stringify({ limit }),
    }),
  syncInstagram: (limit = 30) =>
    apiFetch<SyncMetricsResponse>("/api/posts/sync-instagram", {
      method: "POST",
      body: JSON.stringify({ limit }),
    }),
  getScheduler: () => apiFetch<SchedulerState>("/api/scheduler"),
  saveSchedulerConfig: (config: SchedulerConfig) =>
    apiFetch<{ saved: boolean }>("/api/scheduler/config", {
      method: "POST",
      body: JSON.stringify(config),
    }),
  addQueueItem: (payload: {
    scheduled_date: string;
    topic?: string;
    template?: number;
    scheduled_time?: string;
  }) =>
    apiFetch<{ id: number; scheduled_date: string }>("/api/scheduler/queue", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  removeQueueItem: (id: number) =>
    apiFetch<{ deleted: boolean }>(`/api/scheduler/queue/${id}`, {
      method: "DELETE",
    }),
  autoFillQueue: (payload: { days?: number } = {}) =>
    apiFetch<{
      created: Array<{ id: number; scheduled_date: string }>;
      skipped_existing: number;
      skipped_disabled: number;
    }>("/api/scheduler/queue/auto-fill", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
