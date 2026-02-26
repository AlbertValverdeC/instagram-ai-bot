import type { PostRecord } from '../../types';

interface PostsHistoryProps {
  posts: PostRecord[];
  loading: boolean;
  dbStatusText: string;
  dbStatusColor: 'green' | 'orange' | 'red' | 'dim';
  syncMessage: string;
  syncColor: 'green' | 'orange' | 'red' | 'dim';
  syncing: boolean;
  onSync: () => void;
  onRetry: (postId: number) => void;
}

function fmtDate(iso?: string | null): string {
  if (!iso) {
    return '-';
  }
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function fmtNum(value: unknown): string {
  if (value === null || value === undefined || value === '') {
    return '-';
  }
  const n = Number(value);
  if (Number.isNaN(n)) {
    return String(value);
  }
  return n.toLocaleString();
}

function statusLabel(status?: string): string {
  const labels: Record<string, string> = {
    generated: 'generado (pendiente)',
    publish_error: 'error al publicar',
    published_active: 'publicado (activo)',
    published_deleted: 'publicado (borrado en IG)',
    published: 'publicado'
  };
  return labels[status || ''] || status || '-';
}

function statusClass(status?: string): string {
  if (status === 'published_active' || status === 'published') {
    return 'bg-green/15 text-green';
  }
  if (status === 'published_deleted') {
    return 'bg-orange/15 text-orange';
  }
  if (status === 'publish_error') {
    return 'bg-red/15 text-red';
  }
  return 'bg-dim/15 text-dim';
}

function canRetry(status?: string): boolean {
  return status === 'generated' || status === 'publish_error';
}

function textColor(color: 'green' | 'orange' | 'red' | 'dim'): string {
  if (color === 'green') return 'text-green';
  if (color === 'orange') return 'text-orange';
  if (color === 'red') return 'text-red';
  return 'text-dim';
}

export function PostsHistory({
  posts,
  loading,
  dbStatusText,
  dbStatusColor,
  syncMessage,
  syncColor,
  syncing,
  onSync,
  onRetry
}: PostsHistoryProps) {
  return (
    <section className="mb-5 rounded-xl border border-border bg-card p-5">
      <div className="mb-2 flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-dim">Publicaciones (DB)</h2>
        <button
          type="button"
          onClick={onSync}
          disabled={syncing}
          className="rounded-lg border border-border bg-code px-3 py-1.5 text-sm font-semibold text-text transition hover:border-accent hover:text-accent disabled:cursor-not-allowed disabled:opacity-40"
        >
          📈 Sync IG
        </button>
      </div>

      <p className={`mb-2 text-sm ${textColor(dbStatusColor)}`}>{dbStatusText}</p>
      {syncMessage ? <p className={`mb-2 text-sm ${textColor(syncColor)}`}>{syncMessage}</p> : null}

      {loading ? (
        <p className="text-sm italic text-dim">Cargando...</p>
      ) : posts.length === 0 ? (
        <p className="text-sm italic text-dim">Sin publicaciones registradas aún.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[1400px] border-collapse text-left text-xs">
            <thead>
              <tr className="text-[11px] uppercase tracking-wide text-dim">
                <th className="border-b border-white/10 px-2 py-2">Fecha</th>
                <th className="border-b border-white/10 px-2 py-2">Tema</th>
                <th className="border-b border-white/10 px-2 py-2">Estado</th>
                <th className="border-b border-white/10 px-2 py-2">Estado IG</th>
                <th className="border-b border-white/10 px-2 py-2">Virality</th>
                <th className="border-b border-white/10 px-2 py-2">Intentos</th>
                <th className="border-b border-white/10 px-2 py-2">Fuentes</th>
                <th className="border-b border-white/10 px-2 py-2">Error</th>
                <th className="border-b border-white/10 px-2 py-2">Likes</th>
                <th className="border-b border-white/10 px-2 py-2">Comentarios</th>
                <th className="border-b border-white/10 px-2 py-2">Reach</th>
                <th className="border-b border-white/10 px-2 py-2">ER</th>
                <th className="border-b border-white/10 px-2 py-2">Métricas/Sync</th>
                <th className="border-b border-white/10 px-2 py-2">IG Media ID</th>
                <th className="border-b border-white/10 px-2 py-2">Acción</th>
              </tr>
            </thead>
            <tbody>
              {posts.map((post) => {
                const errorCode = post.last_error_code ? ` (${post.last_error_code})` : '';
                return (
                  <tr key={post.id}>
                    <td className="border-b border-white/5 px-2 py-2">{fmtDate((post.published_at as string) || (post.created_at as string))}</td>
                    <td className="border-b border-white/5 px-2 py-2">{String(post.topic || '-')}</td>
                    <td className="border-b border-white/5 px-2 py-2">
                      <span className={`inline-block rounded-full px-2 py-1 text-[11px] ${statusClass(post.status as string)}`}>
                        {statusLabel(post.status as string)}
                      </span>
                    </td>
                    <td className="border-b border-white/5 px-2 py-2">
                      <span className="inline-block rounded-full border border-border bg-code px-2 py-1 text-[11px] text-dim">
                        {String(post.ig_status || '-')}
                      </span>
                    </td>
                    <td className="border-b border-white/5 px-2 py-2">{post.virality_score ?? '-'}</td>
                    <td className="border-b border-white/5 px-2 py-2">{post.publish_attempts ?? 0}</td>
                    <td className="border-b border-white/5 px-2 py-2">{post.source_count ?? 0}</td>
                    <td className="border-b border-white/5 px-2 py-2">
                      {(post.last_error_tag || '-') + errorCode}
                      <div className="text-dim">{String(post.last_error_message || '-')}</div>
                    </td>
                    <td className="border-b border-white/5 px-2 py-2">{fmtNum(post.likes)}</td>
                    <td className="border-b border-white/5 px-2 py-2">{fmtNum(post.comments)}</td>
                    <td className="border-b border-white/5 px-2 py-2">{fmtNum(post.reach)}</td>
                    <td className="border-b border-white/5 px-2 py-2">
                      {post.engagement_rate == null ? '-' : `${Number(post.engagement_rate).toFixed(2)}%`}
                    </td>
                    <td className="border-b border-white/5 px-2 py-2">
                      {fmtDate(post.metrics_collected_at as string)}
                      <div className="text-dim">IG: {fmtDate(post.ig_last_checked_at as string)}</div>
                    </td>
                    <td className="border-b border-white/5 px-2 py-2 font-mono">{String(post.ig_media_id || '-')}</td>
                    <td className="border-b border-white/5 px-2 py-2">
                      {canRetry(post.status as string) ? (
                        <button
                          type="button"
                          onClick={() => onRetry(post.id)}
                          className="rounded-md border border-border bg-code px-2 py-1 text-xs font-semibold text-text transition hover:border-accent hover:text-accent"
                        >
                          ↻ Reintentar
                        </button>
                      ) : (
                        '-'
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
