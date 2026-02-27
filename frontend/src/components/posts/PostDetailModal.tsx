import type { PostRecord } from "../../types";

interface PostDetailModalProps {
  open: boolean;
  post: PostRecord | null;
  loading: boolean;
  onClose: () => void;
  onPublish: (postId: number) => void;
}

function jsonPreview(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value ?? "");
  }
}

export function PostDetailModal({ open, post, loading, onClose, onPublish }: PostDetailModalProps) {
  if (!open) return null;

  const status = String(post?.status || "");
  const canPublish = status === "draft";

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/70 p-4">
      <div className="max-h-[90vh] w-full max-w-5xl overflow-hidden rounded-xl border border-border-dark bg-secondary-dark shadow-2xl">
        <div className="flex items-center justify-between border-b border-border-dark bg-surface-dark/70 px-6 py-4">
          <h3 className="text-lg font-bold text-white">Detalle publicación</h3>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-border-dark px-3 py-1 text-sm text-text-subtle transition hover:text-white"
          >
            Cerrar
          </button>
        </div>

        <div className="max-h-[calc(90vh-72px)] overflow-auto p-6">
          {loading ? (
            <p className="text-sm italic text-text-subtle">Cargando...</p>
          ) : !post ? (
            <p className="text-sm italic text-text-subtle">No se pudo cargar el post.</p>
          ) : (
            <div className="space-y-5">
              <div className="rounded-lg border border-border-dark bg-surface-dark p-4">
                <p className="text-xs uppercase tracking-wide text-text-subtle">Meta</p>
                <p className="mt-2 text-sm text-white">
                  #{post.id} · {String(post.status || "-")}
                </p>
                <p className="mt-1 text-sm text-slate-300">{String(post.topic || "-")}</p>
                {canPublish && (
                  <button
                    type="button"
                    onClick={() => onPublish(post.id)}
                    className="mt-3 rounded-md border border-emerald-500/40 bg-emerald-500/10 px-3 py-1.5 text-xs font-semibold text-emerald-300 transition hover:border-emerald-400 hover:text-emerald-200"
                  >
                    Publicar en IG
                  </button>
                )}
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <section className="rounded-lg border border-border-dark bg-surface-dark p-4">
                  <p className="mb-2 text-xs uppercase tracking-wide text-text-subtle">
                    Propuesta seleccionada
                  </p>
                  <pre className="overflow-auto whitespace-pre-wrap text-xs text-slate-300">
                    {jsonPreview(post.proposal_payload)}
                  </pre>
                </section>
                <section className="rounded-lg border border-border-dark bg-surface-dark p-4">
                  <p className="mb-2 text-xs uppercase tracking-wide text-text-subtle">
                    Topic payload
                  </p>
                  <pre className="overflow-auto whitespace-pre-wrap text-xs text-slate-300">
                    {jsonPreview(post.topic_payload)}
                  </pre>
                </section>
              </div>

              <section className="rounded-lg border border-border-dark bg-surface-dark p-4">
                <p className="mb-2 text-xs uppercase tracking-wide text-text-subtle">
                  Content payload
                </p>
                <pre className="overflow-auto whitespace-pre-wrap text-xs text-slate-300">
                  {jsonPreview(post.content_payload)}
                </pre>
              </section>

              <section className="rounded-lg border border-border-dark bg-surface-dark p-4">
                <p className="mb-2 text-xs uppercase tracking-wide text-text-subtle">
                  Strategy payload
                </p>
                <pre className="overflow-auto whitespace-pre-wrap text-xs text-slate-300">
                  {jsonPreview(post.strategy_payload)}
                </pre>
              </section>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
