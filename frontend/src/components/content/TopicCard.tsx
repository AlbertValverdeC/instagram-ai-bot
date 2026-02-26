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
      <section className="rounded-xl border border-border bg-card p-5">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-dim">Último Topic</h2>
        <p className="text-sm italic text-dim">Sin topic. Ejecuta el pipeline para generar uno.</p>
      </section>
    );
  }

  const virality = Number(topic.virality_score ?? 0);
  const viralityColor = virality >= 8 ? 'text-green bg-green/15' : virality >= 6 ? 'text-orange bg-orange/15' : 'text-dim bg-dim/15';

  return (
    <section className="rounded-xl border border-border bg-card p-5">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-dim">Último Topic</h2>
      <h3 className="mb-2 text-xl font-semibold leading-tight text-text">{esc(topic.topic || 'Sin título')}</h3>
      <div className="mb-3 flex flex-wrap items-center gap-3 text-sm text-dim">
        <span className={`rounded-full px-3 py-1 text-xs font-semibold ${viralityColor}`}>Virality: {topic.virality_score ?? '?'} / 10</span>
        <span>{esc(topic.topic_en || '')}</span>
      </div>
      {topic.why ? <p className="mb-3 text-sm text-dim">{esc(topic.why)}</p> : null}
      <ul className="space-y-2 text-sm text-dim">
        {(topic.key_points || []).map((point, index) => (
          <li key={`${point}-${index}`} className="border-b border-white/5 pb-2">
            <span className="mr-1 font-bold text-accent">→</span>
            {esc(point)}
          </li>
        ))}
      </ul>
    </section>
  );
}
