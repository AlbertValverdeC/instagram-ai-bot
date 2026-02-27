import { useMemo, useState } from "react";

import type { PostRecord } from "../../types";

type FilterKey = "all" | "published" | "scheduled" | "drafts";
type SortKey = "newest" | "oldest";
type PublishUiState = {
  status: "publishing" | "success" | "error";
  progress: number;
  error?: string;
  updatedAt: number;
};

interface PostsHistoryProps {
  posts: PostRecord[];
  loading: boolean;
  dbStatusText: string;
  dbStatusColor: "green" | "orange" | "red" | "dim";
  publishUi?: Record<number, PublishUiState>;
  syncing: boolean;
  onSync: () => void;
  onPublish: (postId: number) => void;
  onRetry: (postId: number) => void;
  onOpen: (postId: number) => void;
  onBack?: () => void;
}

const FILTERS: Array<{ key: FilterKey; label: string }> = [
  { key: "all", label: "Todo" },
  { key: "published", label: "Publicado" },
  { key: "scheduled", label: "Programado" },
  { key: "drafts", label: "Borradores" },
];

function fmtDate(iso?: string | null): string {
  if (!iso) return "Sin fecha";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function fmtNum(value: unknown): string {
  if (value === null || value === undefined || value === "") return "-";
  const n = Number(value);
  if (Number.isNaN(n)) return String(value);
  return n.toLocaleString();
}

function statusLabel(status?: string): string {
  const labels: Record<string, string> = {
    draft: "DRAFT",
    generated: "SCHEDULED",
    publish_error: "FAILED",
    published_active: "PUBLISHED",
    published_deleted: "DELETED",
    published: "PUBLISHED",
  };
  return labels[status || ""] || (status || "UNKNOWN").toUpperCase();
}

function statusClass(status?: string): string {
  if (status === "published_active" || status === "published") {
    return "border-emerald-400/35 bg-emerald-400/15 text-emerald-300";
  }
  if (status === "generated") {
    return "border-orange/35 bg-orange/15 text-orange";
  }
  if (status === "draft") {
    return "border-sky-300/35 bg-sky-300/10 text-sky-200";
  }
  if (status === "publish_error") {
    return "border-red/35 bg-red/20 text-red";
  }
  return "border-border-dark bg-surface-dark text-text-subtle";
}

function canRetry(status?: string): boolean {
  return status === "generated" || status === "publish_error";
}

function canPublish(status?: string): boolean {
  return status === "draft";
}

function textColor(color: "green" | "orange" | "red" | "dim"): string {
  if (color === "green") return "text-emerald-300";
  if (color === "orange") return "text-orange";
  if (color === "red") return "text-red";
  return "text-text-subtle";
}

function postDateTs(post: PostRecord): number {
  const raw = String(post.published_at || post.created_at || "");
  const value = Date.parse(raw);
  return Number.isFinite(value) ? value : 0;
}

function matchesFilter(post: PostRecord, filter: FilterKey): boolean {
  const status = String(post.status || "");
  if (filter === "all") return true;
  if (filter === "published") return status === "published" || status === "published_active";
  if (filter === "scheduled") return status === "generated";
  if (filter === "drafts") return status === "draft";
  return true;
}

function matchesSearch(post: PostRecord, query: string): boolean {
  if (!query.trim()) return true;
  const q = query.trim().toLowerCase();
  const topic = String(post.topic || "").toLowerCase();
  const status = statusLabel(String(post.status || "")).toLowerCase();
  const error = String(post.last_error_message || "").toLowerCase();
  return topic.includes(q) || status.includes(q) || error.includes(q);
}

function slideSrc(ref: string): string {
  const value = String(ref || "").trim();
  if (!value) return "";
  if (value.startsWith("http://") || value.startsWith("https://")) return value;
  return `/slides/${value.replace(/^\/+/, "")}`;
}

function coverSlideRef(post: PostRecord): string | null {
  const preview = Array.isArray(post.history_preview_slides) ? post.history_preview_slides : [];
  const all = Array.isArray(post.history_slides) ? post.history_slides : [];
  const source = preview.length > 0 ? preview : all;
  for (const raw of source) {
    const ref = String(raw || "").trim();
    if (!ref) continue;
    return ref;
  }
  return null;
}

export function PostsHistory({
  posts,
  loading,
  dbStatusText,
  dbStatusColor,
  publishUi,
  syncing,
  onSync,
  onPublish,
  onRetry,
  onOpen,
  onBack,
}: PostsHistoryProps) {
  const [filter, setFilter] = useState<FilterKey>("all");
  const [sort, setSort] = useState<SortKey>("newest");
  const [query, setQuery] = useState("");
  const [expandedErrors, setExpandedErrors] = useState<Record<number, boolean>>({});

  const visiblePosts = useMemo(() => {
    const base = posts
      .filter((post) => matchesFilter(post, filter))
      .filter((post) => matchesSearch(post, query));
    base.sort((a, b) => {
      const diff = postDateTs(b) - postDateTs(a);
      return sort === "newest" ? diff : -diff;
    });
    return base;
  }, [posts, filter, query, sort]);

  return (
    <section className="min-h-[calc(100vh-110px)] border border-border-dark bg-background-dark">
      <div className="sticky top-0 z-20 border-b border-border-dark bg-secondary-dark/95 px-4 py-4 backdrop-blur-sm sm:px-6">
        <div className="flex items-center justify-between gap-3">
          <div className="flex min-w-0 items-center gap-3">
            {onBack && (
              <button
                type="button"
                onClick={onBack}
                className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-border-dark bg-surface-dark text-text-subtle transition hover:text-white"
                aria-label="Volver al panel principal"
              >
                <span className="material-symbols-outlined text-[20px]">arrow_back</span>
              </button>
            )}
            <div className="min-w-0">
              <h2 className="truncate font-display text-2xl font-bold tracking-tight text-white">
                Historial de publicaciones
              </h2>
              <p className={`text-xs ${textColor(dbStatusColor)}`}>{dbStatusText}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onSync}
            disabled={syncing}
            data-loading={syncing ? "true" : undefined}
            className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-primary/30 bg-primary/10 text-primary transition hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-50"
            aria-label="Sincronizar métricas"
          >
            <span className={`material-symbols-outlined text-[20px] ${syncing ? "animate-spin" : ""}`}>
              sync
            </span>
          </button>
        </div>

        <div className="mt-4 flex gap-2 overflow-x-auto pb-1">
          {FILTERS.map((item) => {
            const active = item.key === filter;
            return (
              <button
                key={item.key}
                type="button"
                onClick={() => setFilter(item.key)}
                className={`whitespace-nowrap rounded-lg border px-3 py-1.5 text-sm font-semibold transition ${
                  active
                    ? "border-primary bg-primary/15 text-primary"
                    : "border-border-dark bg-surface-dark text-text-subtle hover:border-primary/35 hover:text-white"
                }`}
              >
                {item.label}
              </button>
            );
          })}
        </div>

        <div className="mt-3 flex items-center gap-2">
          <label className="flex flex-1 items-center gap-2 rounded-lg border border-border-dark bg-surface-dark px-3 py-2 text-sm transition focus-within:border-primary/45">
            <span className="material-symbols-outlined text-[18px] text-text-subtle">search</span>
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Buscar tema o error..."
              className="w-full bg-transparent text-sm text-white outline-none placeholder:text-text-subtle/70"
            />
          </label>
          <button
            type="button"
            onClick={() => setSort((prev) => (prev === "newest" ? "oldest" : "newest"))}
            className="inline-flex items-center gap-1 rounded-lg border border-border-dark bg-surface-dark px-3 py-2 text-sm font-semibold text-text-subtle transition hover:border-primary/30 hover:text-white"
          >
            {sort === "newest" ? "Más nuevos" : "Más antiguos"}
            <span className="material-symbols-outlined text-[18px]">expand_more</span>
          </button>
        </div>

        <p className="mt-2 text-xs font-semibold uppercase tracking-[0.16em] text-text-subtle">
          {visiblePosts.length} posts encontrados
        </p>
      </div>

      <div className="px-4 sm:px-6">
        {loading ? (
          <p className="py-8 text-center text-sm italic text-text-subtle">Cargando historial...</p>
        ) : visiblePosts.length === 0 ? (
          <p className="py-8 text-center text-sm italic text-text-subtle">
            No hay publicaciones para este filtro.
          </p>
        ) : (
          visiblePosts.map((post) => {
            const status = String(post.status || "");
            const coverSlide = coverSlideRef(post);
            const publishState = publishUi?.[post.id];
            const publishProgress = Math.max(
              0,
              Math.min(100, Math.round(Number(publishState?.progress || 0))),
            );
            const isPublishing = publishState?.status === "publishing";
            const backendError = String(post.last_error_message || "").trim();
            const publishError = String(publishState?.error || "").trim();
            const effectiveError =
              publishState?.status === "error" ? publishError || backendError : backendError;
            const hasError = Boolean(effectiveError);
            const errorExpanded = Boolean(expandedErrors[post.id]);
            const dateText = fmtDate((post.published_at as string) || (post.created_at as string));
            const showPrimaryAction = canPublish(status) || canRetry(status);
            const actionLabel = canPublish(status)
              ? isPublishing
                ? "Publicando"
                : "Publicar"
              : "Retry";
            const actionClass = canPublish(status)
              ? "border-emerald-400/40 bg-emerald-400/20 text-emerald-300 hover:bg-emerald-400/30"
              : "border-red/40 bg-red/25 text-red hover:bg-red/35";
            const actionHandler = canPublish(status) ? onPublish : onRetry;

            return (
              <article key={post.id} className="border-b border-orange/15 py-3">
                <div className="flex items-start gap-2.5">
                  <button
                    type="button"
                    onClick={() => onOpen(post.id)}
                    className="h-16 w-12 shrink-0 overflow-hidden rounded-md border border-orange/25 bg-black/30"
                    aria-label={`Abrir post ${post.id}`}
                  >
                    {coverSlide ? (
                      <img
                        src={slideSrc(coverSlide)}
                        alt={`Slide principal ${post.id}`}
                        loading="lazy"
                        className="h-full w-full object-cover"
                      />
                    ) : (
                      <span className="block h-full w-full bg-gradient-to-br from-[#ff9d00] via-[#ff6a3d] to-[#8949ff]" />
                    )}
                  </button>

                  <div className="min-w-0 flex-1">
                    <div className="flex items-start justify-between gap-2">
                      <p className="line-clamp-2 text-base font-semibold leading-tight text-white">
                        {String(post.topic || "Sin tema")}
                      </p>
                      <span
                        className={`inline-flex shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-bold tracking-wide ${statusClass(status)}`}
                      >
                        {statusLabel(status)}
                      </span>
                    </div>

                    <div className="mt-0.5 flex items-center justify-between gap-2">
                      <p className="text-xs text-slate-300">{dateText}</p>
                      {hasError && (
                        <button
                          type="button"
                          onClick={() =>
                            setExpandedErrors((prev) => ({
                              ...prev,
                              [post.id]: !prev[post.id],
                            }))
                          }
                          className="inline-flex h-6 w-6 items-center justify-center rounded border border-red/40 bg-red/10 text-red transition hover:bg-red/20"
                          aria-label={errorExpanded ? "Ocultar error" : "Ver error"}
                          title={errorExpanded ? "Ocultar error" : "Ver error"}
                        >
                          <span className="material-symbols-outlined text-[15px]">
                            {errorExpanded ? "expand_less" : "error"}
                          </span>
                        </button>
                      )}
                    </div>

                    {publishState?.status === "publishing" && (
                      <div className="mt-1.5 h-[2px] overflow-hidden rounded-full bg-white/10">
                        <div
                          className="h-full rounded-full bg-primary transition-all duration-500"
                          style={{ width: `${publishProgress}%` }}
                        />
                      </div>
                    )}

                    {hasError && errorExpanded && (
                      <pre className="mt-1.5 max-h-28 overflow-auto whitespace-pre-wrap rounded border border-red/35 bg-red/10 p-2 text-[11px] text-red">
                        {effectiveError}
                      </pre>
                    )}

                    <div className="mt-2 flex items-center justify-between gap-2">
                      <div className="flex items-center gap-3 text-xs text-slate-300">
                        <span className="inline-flex items-center gap-1">
                          <span className="material-symbols-outlined text-[16px]">favorite</span>
                          {fmtNum(post.likes)}
                        </span>
                        <span className="inline-flex items-center gap-1">
                          <span className="material-symbols-outlined text-[16px]">chat_bubble</span>
                          {fmtNum(post.comments)}
                        </span>
                        <span className="hidden items-center gap-1 sm:inline-flex">
                          <span className="material-symbols-outlined text-[16px]">visibility</span>
                          {fmtNum(post.reach)}
                        </span>
                      </div>

                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() => onOpen(post.id)}
                          className="rounded-lg border border-border-dark bg-black/25 px-3 py-1.5 text-xs font-semibold text-text-subtle transition hover:border-orange/30 hover:text-white"
                        >
                          Abrir
                        </button>
                        {showPrimaryAction && (
                          <button
                            type="button"
                            onClick={() => actionHandler(post.id)}
                            disabled={isPublishing}
                            data-loading={isPublishing ? "true" : undefined}
                            className={`rounded-lg border px-3 py-1.5 text-xs font-semibold transition disabled:cursor-not-allowed disabled:opacity-45 ${actionClass}`}
                          >
                            {actionLabel}
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              </article>
            );
          })
        )}
      </div>
    </section>
  );
}
