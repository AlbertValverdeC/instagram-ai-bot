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
  { label: '', value: 0, style: 'bg-gradient-to-br from-[#4338ca] to-[#1e3a8a]' },
  { label: '', value: 1, style: 'bg-gradient-to-br from-[#ec4899] to-[#e11d48]' },
  { label: '', value: 2, style: 'bg-gradient-to-br from-[#10b981] to-[#0f766e]' },
  { label: '', value: 3, style: 'bg-gradient-to-br from-[#f97316] to-[#d97706]' },
  { label: '', value: 4, style: 'bg-gradient-to-br from-[#1c2630] to-[#0a0f1a]' },
];

export function Controls({
  running,
  topic,
  selectedTemplate,
  onTopicChange,
  onSelectTemplate,
  onRun,
  onSearchTopic,
}: ControlsProps) {
  return (
    <section className="mb-6 flex flex-col gap-6 rounded-xl border border-border-dark bg-secondary-dark p-4 xl:flex-row xl:items-center xl:justify-between">
      <div className="flex flex-wrap items-center gap-3">
        {/* Mode buttons */}
        <div className="flex rounded-lg border border-border-dark bg-surface-dark p-1">
          <button
            type="button"
            disabled={running}
            onClick={() => onRun('test')}
            title="Usa datos de ejemplo (sin llamadas a APIs). Ideal para probar el diseño visual sin gastar créditos."
            className="rounded-md px-4 py-2 text-sm font-medium text-text-subtle transition-colors hover:bg-border-dark hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
          >
            Test Mode
          </button>
          <button
            type="button"
            disabled={running}
            onClick={() => onRun('dry-run')}
            title="Ejecuta el pipeline completo con APIs reales, pero NO publica en Instagram."
            className="rounded-md px-4 py-2 text-sm font-medium text-text-subtle transition-colors hover:bg-border-dark hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
          >
            Dry Run
          </button>
          <button
            type="button"
            disabled={running}
            onClick={() => onRun('live')}
            title="Pipeline completo + publicación real en Instagram. Requiere todas las API keys configuradas."
            className="rounded-md border border-red-500/50 bg-red-500/10 px-4 py-2 text-sm font-bold text-red-400 shadow-[0_0_10px_rgba(239,68,68,0.2)] disabled:cursor-not-allowed disabled:opacity-40"
          >
            Live Bot
          </button>
        </div>

        <div className="hidden h-8 w-px bg-border-dark sm:block" />

        {/* Topic input */}
        <div className="flex min-w-[300px] flex-1 items-center gap-3">
          <div className="group relative flex-1">
            <span className="absolute inset-y-0 left-0 flex items-center pl-3 text-text-subtle transition-colors group-focus-within:text-primary">
              <span className="material-symbols-outlined">search</span>
            </span>
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
              className="w-full rounded-lg border border-border-dark bg-surface-dark py-2.5 pl-10 pr-3 text-sm text-white placeholder-text-subtle/50 transition-all focus:border-primary focus:ring-1 focus:ring-primary"
            />
          </div>
          <button
            type="button"
            disabled={running}
            onClick={onSearchTopic}
            className="flex items-center gap-2 rounded-lg bg-primary px-5 py-2.5 text-sm font-bold text-background-dark transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <span className="material-symbols-outlined text-[18px]">auto_awesome</span>
            Generar
          </button>
        </div>
      </div>

      {/* Templates */}
      <div className="flex w-full items-center gap-4 overflow-x-auto pb-2 xl:w-auto xl:pb-0">
        <span className="whitespace-nowrap text-xs font-medium uppercase tracking-wider text-text-subtle">Templates</span>
        <div className="flex gap-2">
          {templates.map((tpl) => {
            const active = selectedTemplate === tpl.value;
            return (
              <button
                key={tpl.value === null ? 'auto' : tpl.value}
                type="button"
                disabled={running}
                onClick={() => onSelectTemplate(tpl.value)}
                className={`relative size-10 rounded-lg border transition-opacity ${
                  active
                    ? 'ring-2 ring-primary ring-offset-2 ring-offset-secondary-dark'
                    : 'border-transparent opacity-50 hover:border-white/20 hover:opacity-100'
                } ${tpl.style || 'border-border-dark bg-surface-dark'} flex items-center justify-center text-xs font-bold text-text-subtle`}
                title={tpl.value === null ? 'Auto — Rota automáticamente' : `Template ${tpl.value}`}
              >
                {tpl.label}
                {active && tpl.value !== null && (
                  <div className="absolute -right-1 -top-1 size-3 rounded-full border border-secondary-dark bg-primary" />
                )}
              </button>
            );
          })}
        </div>
      </div>
    </section>
  );
}
