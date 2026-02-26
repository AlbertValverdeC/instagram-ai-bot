export type PipelineStatus = 'idle' | 'running' | 'done' | 'error';

export interface TopicPayload {
  topic?: string;
  topic_en?: string;
  virality_score?: number;
  why?: string;
  key_points?: string[];
  source_urls?: string[];
  [key: string]: unknown;
}

export interface ContentPayload {
  slides?: Array<{ type?: string; title?: string; body?: string }>;
  caption?: string;
  [key: string]: unknown;
}

export interface ApiStateResponse {
  topic: TopicPayload | null;
  content: ContentPayload | null;
  slides: string[];
  history_count: number;
}

export interface ApiStatusResponse {
  status: PipelineStatus;
  output: string;
  error_summary?: string | null;
  mode?: string | null;
  elapsed?: number | null;
}

export interface RunResponse {
  status: string;
  mode?: string;
  elapsed?: number | null;
  error_summary?: string | null;
  output_tail?: string;
  topic?: string;
}

export interface ApiKeyItem {
  key: string;
  label: string;
  hint: string;
  placeholder: string;
  required: boolean;
  group: string;
  url?: string;
  secret: boolean;
  value: string;
  configured: boolean;
}

export interface PromptItem {
  id: string;
  name: string;
  description: string;
  category: string;
  type: 'meta' | 'fallback' | string;
  module: string;
  variables: string[];
  what_it_does?: string;
  when_it_runs?: string;
  if_you_change_it?: string;
  risk_level?: string;
  text: string;
  default_text: string;
  custom: boolean;
}

export interface ResearchConfig {
  subreddits: string[];
  rss_feeds: string[];
  trends_keywords: string[];
  newsapi_domains: string;
}

export interface ResearchConfigResponse {
  config: ResearchConfig;
  custom: boolean;
  defaults: ResearchConfig;
}

export interface PostRecord {
  id: number;
  topic?: string;
  status?: string;
  ig_status?: string;
  virality_score?: number | null;
  publish_attempts?: number;
  source_count?: number;
  last_error_tag?: string | null;
  last_error_code?: string | null;
  last_error_message?: string | null;
  likes?: number | null;
  comments?: number | null;
  reach?: number | null;
  engagement_rate?: number | null;
  metrics_collected_at?: string | null;
  ig_last_checked_at?: string | null;
  ig_media_id?: string | null;
  published_at?: string | null;
  created_at?: string | null;
  [key: string]: unknown;
}

export interface PostsResponse {
  posts: PostRecord[];
}

export interface DbStatusResponse {
  warning?: string;
  dialect?: string;
  persistent_ok?: boolean;
  [key: string]: unknown;
}

export interface SyncMetricsResponse {
  checked?: number;
  updated?: number;
  failed?: number;
  pending_checked?: number;
  pending_reconciled?: number;
  auto_interval_minutes?: number;
  [key: string]: unknown;
}
