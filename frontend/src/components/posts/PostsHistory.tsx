import type { PostRecord } from "../../types";

interface PostsHistoryProps {
  posts: PostRecord[];
  loading: boolean;
  dbStatusText: string;
  dbStatusColor: "green" | "orange" | "red" | "dim";
  syncing: boolean;
  onSync: () => void;
  onPublish: (postId: number) => void;
  onRetry: (postId: number) => void;
  onOpen: (postId: number) => void;
}

function fmtDate(iso?: string | null): string {
  if (!iso) return "-";
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
    draft: "draft",
    generated: "pendiente",
    publish_error: "error",
    published_active: "activo",
    published_deleted: "borrado",
    published: "publicado",
  };
  return labels[status || ""] || status || "-";
}

function statusClass(status?: string): string {
  if (status === "draft") return "bg-sky-400/10 text-sky-300 border-sky-400/20";
  if (status === "published_active" || status === "published")
    return "bg-emerald-400/10 text-emerald-400 border-emerald-400/20";
  if (status === "published_deleted") return "bg-orange/10 text-orange border-orange/20";
  if (status === "publish_error") return "bg-red/10 text-red border-red/20";
  return "bg-text-subtle/10 text-text-subtle border-text-subtle/20";
}

function canRetry(status?: string): boolean {
  return status === "generated" || status === "publish_error";
}

function canPublish(status?: string): boolean {
  return status === "draft";
}

function textColor(color: "green" | "orange" | "red" | "dim"): string {
  if (color === "green") return "text-emerald-400";
  if (color === "orange") return "text-orange";
  if (color === "red") return "text-red";
  return "text-text-subtle";
}

export function PostsHistory({
  posts,
  loading,
  dbStatusText,
  dbStatusColor,
  syncing,
  onSync,
  onPublish,
  onRetry,
  onOpen,
}: PostsHistoryProps) {
  return (
    <section className="mb-6 overflow-hidden rounded-xl border border-border-dark bg-secondary-dark shadow-lg">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border-dark bg-surface-dark/50 px-6 py-4">
        <div className="flex items-center gap-3">
          <h2 className="flex items-center gap-2 text-lg font-bold text-white">
            <span className="material-symbols-outlined text-primary">database</span>
            Publicaciones
          </h2>
          <span className="rounded-full border border-border-dark bg-surface-dark px-2 py-0.5 text-xs font-medium text-text-subtle">
            {posts.length}
          </span>
        </div>
        <button
          type="button"
          onClick={onSync}
          disabled={syncing}
          className="flex items-center gap-2 rounded-lg bg-primary/10 px-4 py-2 text-sm font-semibold text-primary transition hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <span className="material-symbols-outlined text-[18px]">sync</span>
          Sync IG
        </button>
      </div>

      {/* Status messages */}
      <div className="space-y-1 border-b border-border-dark px-6 py-3">
        <p className={`text-xs ${textColor(dbStatusColor)}`}>{dbStatusText}</p>
      </div>

      {/* Table */}
      <div className="p-4">
        {loading ? (
          <p className="py-8 text-center text-sm italic text-text-subtle">Cargando...</p>
        ) : posts.length === 0 ? (
          <p className="py-8 text-center text-sm italic text-text-subtle">
            Sin publicaciones registradas aún.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1200px] border-collapse text-left text-xs">
              <thead>
                <tr className="text-[11px] uppercase tracking-wide text-text-subtle">
                  <th className="border-b border-border-dark px-3 py-3">Fecha</th>
                  <th className="border-b border-border-dark px-3 py-3">Tema</th>
                  <th className="border-b border-border-dark px-3 py-3">Estado</th>
                  <th className="border-b border-border-dark px-3 py-3">IG</th>
                  <th className="border-b border-border-dark px-3 py-3">Viral</th>
                  <th className="border-b border-border-dark px-3 py-3">Likes</th>
                  <th className="border-b border-border-dark px-3 py-3">Comments</th>
                  <th className="border-b border-border-dark px-3 py-3">Reach</th>
                  <th className="border-b border-border-dark px-3 py-3">ER</th>
                  <th className="border-b border-border-dark px-3 py-3">Error</th>
                  <th className="border-b border-border-dark px-3 py-3">Acción</th>
                </tr>
              </thead>
              <tbody>
                {posts.map((post) => (
                  <tr key={post.id} className="transition-colors hover:bg-surface-dark/50">
                    <td className="border-b border-border-dark/50 px-3 py-3 text-text-subtle">
                      {fmtDate((post.published_at as string) || (post.created_at as string))}
                    </td>
                    <td className="max-w-[200px] truncate border-b border-border-dark/50 px-3 py-3 text-white">
                      {String(post.topic || "-")}
                    </td>
                    <td className="border-b border-border-dark/50 px-3 py-3">
                      <span
                        className={`inline-block rounded-full border px-2 py-0.5 text-[10px] font-bold ${statusClass(post.status as string)}`}
                      >
                        {statusLabel(post.status as string)}
                      </span>
                    </td>
                    <td className="border-b border-border-dark/50 px-3 py-3 text-text-subtle">
                      {String(post.ig_status || "-")}
                    </td>
                    <td className="border-b border-border-dark/50 px-3 py-3 text-text-subtle">
                      {post.virality_score ?? "-"}
                    </td>
                    <td className="border-b border-border-dark/50 px-3 py-3 text-text-subtle">
                      {fmtNum(post.likes)}
                    </td>
                    <td className="border-b border-border-dark/50 px-3 py-3 text-text-subtle">
                      {fmtNum(post.comments)}
                    </td>
                    <td className="border-b border-border-dark/50 px-3 py-3 text-text-subtle">
                      {fmtNum(post.reach)}
                    </td>
                    <td className="border-b border-border-dark/50 px-3 py-3 text-text-subtle">
                      {post.engagement_rate == null
                        ? "-"
                        : `${Number(post.engagement_rate).toFixed(2)}%`}
                    </td>
                    <td
                      className="max-w-[150px] truncate border-b border-border-dark/50 px-3 py-3 text-text-subtle"
                      title={String(post.last_error_message || "")}
                    >
                      {post.last_error_tag || "-"}
                    </td>
                    <td className="border-b border-border-dark/50 px-3 py-3">
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() => onOpen(post.id)}
                          className="rounded-md border border-border-dark bg-surface-dark px-3 py-1 text-xs font-semibold text-text-subtle transition hover:border-primary hover:text-primary"
                        >
                          Abrir
                        </button>
                        {canPublish(post.status as string) && (
                          <button
                            type="button"
                            onClick={() => onPublish(post.id)}
                            className="rounded-md border border-emerald-500/40 bg-emerald-500/10 px-3 py-1 text-xs font-semibold text-emerald-300 transition hover:border-emerald-400 hover:text-emerald-200"
                          >
                            Publicar
                          </button>
                        )}
                        {canRetry(post.status as string) && (
                          <button
                            type="button"
                            onClick={() => onRetry(post.id)}
                            className="rounded-md border border-border-dark bg-surface-dark px-3 py-1 text-xs font-semibold text-text-subtle transition hover:border-primary hover:text-primary"
                          >
                            Reintentar
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}
