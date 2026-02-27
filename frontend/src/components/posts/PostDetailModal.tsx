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

function slideSrc(ref: string): string {
  const value = String(ref || "").trim();
  if (!value) return "";
  if (value.startsWith("http://") || value.startsWith("https://")) return value;
  return `/slides/${value.replace(/^\/+/, "")}`;
}

export function PostDetailModal({ open, post, loading, onClose, onPublish }: PostDetailModalProps) {
  if (!open) return null;

  const status = String(post?.status || "");
  const canPublish = status === "draft";
  const historySlides = Array.isArray(post?.history_slides)
    ? post.history_slides.filter((item) => String(item || "").trim())
    : [];

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/70 p-4">
      <div className="max-h-[90vh] w-full max-w-5xl overflow-hidden rounded-xl border border-border-dark bg-secondary-dark shadow-2xl">
        <div className="flex items-center justify-between border-b border-border-dark bg-surface-dark/70 px-6 py-4">
          <h3 className="font-display text-lg font-bold text-white">Detalle publicación</h3>
          <button type="button" onClick={onClose} className="btn-ghost px-3 py-1 text-sm">
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
                    className="btn-success mt-3 px-3 py-1.5 text-xs"
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

              {historySlides.length > 0 && (
                <section className="rounded-lg border border-border-dark bg-surface-dark p-4">
                  <p className="mb-3 text-xs uppercase tracking-wide text-text-subtle">
                    Slides guardadas en historial
                  </p>
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
                    {historySlides.map((slide, idx) => (
                      <a
                        key={`${post.id}-slide-${idx + 1}`}
                        href={slideSrc(slide)}
                        target="_blank"
                        rel="noreferrer"
                        className="group relative aspect-[4/5] overflow-hidden rounded-md border border-border-dark"
                      >
                        <img
                          src={slideSrc(slide)}
                          alt={`Slide ${idx + 1}`}
                          loading="lazy"
                          className="absolute inset-0 h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
                        />
                        <span className="absolute right-1.5 top-1.5 rounded bg-black/70 px-1.5 py-0.5 text-[10px] text-white">
                          {idx + 1}
                        </span>
                      </a>
                    ))}
                  </div>
                </section>
              )}

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
