import type { PipelineStatus } from '../../types';

interface HeaderProps {
  status: PipelineStatus;
  tokenConfigured: boolean;
  tokenInput: string;
  onTokenInputChange: (value: string) => void;
  onSaveToken: () => void;
  onClearToken: () => void;
  onOpenSources: () => void;
  onOpenPrompts: () => void;
  onOpenKeys: () => void;
}

const STATUS_LABELS: Record<PipelineStatus, string> = {
  idle: 'idle',
  running: 'ejecutando...',
  done: 'completado',
  error: 'error'
};

const STATUS_CLASSES: Record<PipelineStatus, string> = {
  idle: 'bg-dim/20 text-dim',
  running: 'bg-orange/20 text-orange',
  done: 'bg-green/20 text-green',
  error: 'bg-red/20 text-red'
};

export function Header({
  status,
  tokenConfigured,
  tokenInput,
  onTokenInputChange,
  onSaveToken,
  onClearToken,
  onOpenSources,
  onOpenPrompts,
  onOpenKeys
}: HeaderProps) {
  return (
    <header className="border-b border-border bg-card px-4 py-5 md:px-8">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-xl font-bold md:text-2xl">
          <span className="text-accent">IG</span> AI Bot
        </h1>

        <span className="rounded-full bg-accent/20 px-3 py-1 text-xs font-semibold text-accent">Panel de Control</span>
        <span className={`rounded-full px-3 py-1 text-xs font-semibold ${STATUS_CLASSES[status]}`}>{STATUS_LABELS[status]}</span>

        <div className="ml-auto flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={onOpenSources}
            className="rounded-lg border border-border bg-code px-3 py-2 text-sm font-semibold text-text transition hover:border-accent hover:text-accent"
            title="Opcional. El flujo normal es escribir un tema y buscar. Este panel es solo para personalización avanzada."
          >
            📡 Fuentes (avanzado)
          </button>
          <button
            type="button"
            onClick={onOpenPrompts}
            className="rounded-lg border border-border bg-code px-3 py-2 text-sm font-semibold text-text transition hover:border-accent hover:text-accent"
            title="Ver y editar los prompts del sistema (investigación, contenido, imagen)."
          >
            ✏️ Prompts
          </button>
          <button
            type="button"
            onClick={onOpenKeys}
            className="rounded-lg border border-border bg-code px-3 py-2 text-sm font-semibold text-text transition hover:border-accent hover:text-accent"
            title="Configurar las claves de API necesarias para el bot."
          >
            🔑 API Keys
          </button>
          <a
            className="rounded-lg border border-border bg-code px-3 py-2 text-sm font-semibold text-text transition hover:border-accent hover:text-accent"
            href="/docs"
            target="_blank"
            rel="noreferrer"
            title="Abrir la documentación completa en otra pestaña."
          >
            📖 Docs
          </a>

          <div className="flex items-center gap-2 rounded-lg border border-border bg-code p-2">
            <input
              type="password"
              value={tokenInput}
              onChange={(e) => onTokenInputChange(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  onSaveToken();
                }
              }}
              placeholder="API token dashboard"
              className="w-48 rounded-md border border-border bg-bg px-2 py-1 text-xs text-text outline-none focus:border-accent"
              title="Solo cloud: token para autorizar APIs del panel. Se guarda localmente en este navegador."
            />
            <button
              type="button"
              onClick={onSaveToken}
              className="rounded-md border border-border bg-bg px-2 py-1 text-xs font-semibold text-text transition hover:border-accent hover:text-accent"
            >
              Guardar
            </button>
            <button
              type="button"
              onClick={onClearToken}
              className="rounded-md border border-border bg-bg px-2 py-1 text-xs font-semibold text-text transition hover:border-accent hover:text-accent"
            >
              Limpiar
            </button>
          </div>

          <span className={`text-xs ${tokenConfigured ? 'text-green' : 'text-dim'}`}>
            Token: {tokenConfigured ? 'configurado' : 'no configurado'}
          </span>
        </div>
      </div>
    </header>
  );
}
