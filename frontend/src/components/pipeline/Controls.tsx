interface ControlsProps {
  running: boolean;
  topic: string;
  selectedTemplate: number | null;
  onTopicChange: (value: string) => void;
  onSelectTemplate: (template: number | null) => void;
  onRun: (mode: 'test' | 'dry-run' | 'live') => void;
  onSearchTopic: () => void;
}

const templates = [
  { label: 'A', value: null, style: '' },
  { label: '', value: 0, style: 'bg-gradient-to-b from-[#0a0f28] to-[#19376d]' },
  { label: '', value: 1, style: 'bg-gradient-to-b from-[#140523] to-[#4b1478]' },
  { label: '', value: 2, style: 'bg-gradient-to-b from-[#05140f] to-[#0f503c]' },
  { label: '', value: 3, style: 'bg-gradient-to-b from-[#0f0f19] to-[#282846]' },
  { label: '', value: 4, style: 'bg-gradient-to-b from-[#050507] to-[#16161c]' }
];

export function Controls({
  running,
  topic,
  selectedTemplate,
  onTopicChange,
  onSelectTemplate,
  onRun,
  onSearchTopic
}: ControlsProps) {
  return (
    <section className="mb-5 flex flex-wrap items-center gap-3 rounded-xl border border-border bg-card p-5">
      <span className="text-xs font-semibold uppercase tracking-wide text-dim">Ejecutar:</span>

      <button
        type="button"
        disabled={running}
        onClick={() => onRun('test')}
        title="Usa datos de ejemplo (sin llamadas a APIs). Ideal para probar el diseño visual sin gastar créditos."
        className="rounded-lg border border-border bg-code px-4 py-2 text-sm font-semibold text-text transition hover:border-accent hover:text-accent disabled:cursor-not-allowed disabled:opacity-40"
      >
        🧪 Test
      </button>
      <button
        type="button"
        disabled={running}
        onClick={() => onRun('dry-run')}
        title="Ejecuta el pipeline completo con APIs reales, pero NO publica en Instagram."
        className="rounded-lg border border-border bg-code px-4 py-2 text-sm font-semibold text-text transition hover:border-accent hover:text-accent disabled:cursor-not-allowed disabled:opacity-40"
      >
        🔍 Dry Run
      </button>
      <button
        type="button"
        disabled={running}
        onClick={() => onRun('live')}
        title="Pipeline completo + publicación real en Instagram. Requiere todas las API keys configuradas."
        className="rounded-lg border border-red bg-code px-4 py-2 text-sm font-semibold text-red transition hover:bg-red/10 disabled:cursor-not-allowed disabled:opacity-40"
      >
        🚀 Live
      </button>

      <div className="mx-1 h-8 w-px bg-border" />

      <input
        value={topic}
        onChange={(e) => onTopicChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            e.preventDefault();
            onSearchTopic();
          }
        }}
        placeholder="Tema objetivo (ej: AGENTES DE IA)"
        title="Opcional: si escribes un tema, el bot investiga tendencias recientes de ese tema en varias fuentes automáticamente."
        className="min-w-[260px] rounded-lg border border-border bg-code px-3 py-2 text-sm text-text outline-none placeholder:text-dim focus:border-accent"
      />
      <button
        type="button"
        disabled={running}
        onClick={onSearchTopic}
        title="Ejecuta solo investigación y guarda el topic en data/last_topic.json, sin generar slides ni publicar."
        className="rounded-lg border border-border bg-code px-4 py-2 text-sm font-semibold text-text transition hover:border-accent hover:text-accent disabled:cursor-not-allowed disabled:opacity-40"
      >
        🔎 Buscar tema
      </button>

      <div className="mx-1 h-8 w-px bg-border" />
      <span className="text-xs font-semibold uppercase tracking-wide text-dim">Template:</span>
      <div className="flex items-center gap-1">
        {templates.map((tpl) => {
          const active = selectedTemplate === tpl.value;
          return (
            <button
              key={tpl.value === null ? 'auto' : tpl.value}
              type="button"
              disabled={running}
              onClick={() => onSelectTemplate(tpl.value)}
              className={`h-9 w-9 rounded-md border-2 text-xs font-bold transition ${
                active ? 'border-accent bg-accent/15 text-text' : 'border-border text-text'
              } ${tpl.style}`}
              title={
                tpl.value === null
                  ? 'Auto — Rota automáticamente entre los 5 templates.'
                  : `Template ${tpl.value}`
              }
            >
              {tpl.label}
            </button>
          );
        })}
      </div>
    </section>
  );
}
