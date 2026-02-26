import type { TopicPayload } from '../../types';

interface TopicCardProps {
  topic: TopicPayload | null;
}

function esc(value: unknown): string {
  return String(value ?? '');
}

export function TopicCard({ topic }: TopicCardProps) {
  if (!topic) {
    return (
      <section className="overflow-hidden rounded-xl border border-border-dark bg-secondary-dark shadow-lg">
        <div className="p-6">
          <p className="text-sm font-medium text-text-subtle">Último Topic Generado</p>
          <p className="mt-3 text-sm italic text-text-subtle">Sin topic. Ejecuta el pipeline para generar uno.</p>
        </div>
      </section>
    );
  }

  const virality = Number(topic.virality_score ?? 0);
  const viralityColor =
    virality >= 8
      ? 'text-emerald-400 bg-emerald-400/10 border-emerald-400/20'
      : virality >= 6
        ? 'text-orange bg-orange/10 border-orange/20'
        : 'text-text-subtle bg-text-subtle/10 border-text-subtle/20';

  return (
    <section className="flex flex-col overflow-hidden rounded-xl border border-border-dark bg-secondary-dark shadow-lg">
      {/* Header */}
      <div className="flex items-start justify-between border-b border-border-dark p-6">
        <div>
          <p className="mb-1 text-sm font-medium text-text-subtle">Último Topic Generado</p>
          <h3 className="text-2xl font-bold text-white">{esc(topic.topic || 'Sin título')}</h3>
        </div>
        <div className="flex flex-col items-end">
          <div className={`flex items-center gap-1 rounded border px-2 py-1 text-xs font-bold ${viralityColor}`}>
            <span className="material-symbols-outlined text-[14px]">trending_up</span>
            {topic.virality_score ?? '?'}/10 Viral Score
          </div>
          {topic.topic_en && <span className="mt-1 text-xs text-text-subtle">{esc(topic.topic_en)}</span>}
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 space-y-6 p-6">
        {topic.why && (
          <div>
            <label className="mb-3 block text-xs font-semibold uppercase tracking-wider text-text-subtle">Descripción</label>
            <p className="text-sm leading-relaxed text-slate-300">{esc(topic.why)}</p>
          </div>
        )}

        {(topic.key_points || []).length > 0 && (
          <div>
            <label className="mb-3 block text-xs font-semibold uppercase tracking-wider text-text-subtle">Strategy Points</label>
            <ul className="space-y-3">
              {(topic.key_points || []).map((point, index) => (
                <li key={`${point}-${index}`} className="flex items-start gap-3 text-sm text-slate-300">
                  <span className="material-symbols-outlined mt-0.5 text-[18px] text-primary">check_circle</span>
                  <span>{esc(point)}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </section>
  );
}
