import type {
  ApiKeyItem,
  ApiStateResponse,
  ApiStatusResponse,
  DbStatusResponse,
  PostsResponse,
  PromptItem,
  ResearchConfig,
  ResearchConfigResponse,
  RunResponse,
  SyncMetricsResponse
} from '../types';

let tokenGetter: (() => string) | null = null;

export function setApiTokenGetter(getter: () => string) {
  tokenGetter = getter;
}

async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers || {});
  if (!headers.has('Content-Type') && init.body) {
    headers.set('Content-Type', 'application/json');
  }

  const token = tokenGetter?.().trim() || '';
  if (token && !headers.has('X-API-Token')) {
    headers.set('X-API-Token', token);
  }

  const response = await fetch(path, { ...init, headers });
  const body = await response.json().catch(() => ({}));

  if (!response.ok) {
    const errorMessage =
      (typeof body?.error === 'string' && body.error) ||
      (typeof body?.error_summary === 'string' && body.error_summary) ||
      `HTTP ${response.status}`;
    const error = new Error(errorMessage) as Error & { status?: number; body?: unknown };
    error.status = response.status;
    error.body = body;
    throw error;
  }

  return body as T;
}

export const apiClient = {
  getState: () => apiFetch<ApiStateResponse>('/api/state'),
  getStatus: () => apiFetch<ApiStatusResponse>('/api/status'),
  runPipeline: (payload: { mode: 'test' | 'dry-run' | 'live'; template?: number; topic?: string }) =>
    apiFetch<RunResponse>('/api/run', {
      method: 'POST',
      body: JSON.stringify(payload)
    }),
  searchTopic: (topic: string) =>
    apiFetch<RunResponse>('/api/search-topic', {
      method: 'POST',
      body: JSON.stringify({ topic })
    }),
  getKeys: () => apiFetch<ApiKeyItem[]>('/api/keys'),
  saveKeys: (payload: Record<string, string>) =>
    apiFetch<{ saved: number }>('/api/keys', {
      method: 'POST',
      body: JSON.stringify(payload)
    }),
  getPrompts: () => apiFetch<PromptItem[]>('/api/prompts'),
  savePrompt: (id: string, text: string) =>
    apiFetch<{ saved: string }>('/api/prompts', {
      method: 'POST',
      body: JSON.stringify({ id, text })
    }),
  resetPrompt: (id: string) =>
    apiFetch<{ reset: string }>('/api/prompts/reset', {
      method: 'POST',
      body: JSON.stringify({ id })
    }),
  getResearchConfig: () => apiFetch<ResearchConfigResponse>('/api/research-config'),
  saveResearchConfig: (config: ResearchConfig) =>
    apiFetch<{ saved: boolean }>('/api/research-config', {
      method: 'POST',
      body: JSON.stringify({ config })
    }),
  resetResearchConfig: () =>
    apiFetch<{ reset: boolean }>('/api/research-config/reset', {
      method: 'POST',
      body: JSON.stringify({})
    }),
  getPosts: (limit = 20) => apiFetch<PostsResponse>(`/api/posts?limit=${limit}`),
  retryPublish: (postId: number) =>
    apiFetch<{ media_id?: string; status?: string }>('/api/posts/' + postId + '/retry-publish', {
      method: 'POST',
      body: JSON.stringify({})
    }),
  getDbStatus: () => apiFetch<DbStatusResponse>('/api/db-status'),
  syncMetrics: (limit = 30) =>
    apiFetch<SyncMetricsResponse>('/api/posts/sync-metrics', {
      method: 'POST',
      body: JSON.stringify({ limit })
    }),
  syncInstagram: (limit = 30) =>
    apiFetch<SyncMetricsResponse>('/api/posts/sync-instagram', {
      method: 'POST',
      body: JSON.stringify({ limit })
    })
};
