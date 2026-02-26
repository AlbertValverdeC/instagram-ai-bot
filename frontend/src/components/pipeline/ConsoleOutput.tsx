import type { PipelineStatus } from '../../types';

interface ConsoleOutputProps {
  status: PipelineStatus;
  elapsed?: number | null;
  output: string;
}

function statusDotClass(status: PipelineStatus): string {
  switch (status) {
    case 'running':
      return 'bg-orange animate-pulse';
    case 'done':
      return 'bg-emerald-500';
    case 'error':
      return 'bg-red';
    default:
      return 'bg-text-subtle/50';
  }
}

export function ConsoleOutput({ status, elapsed, output }: ConsoleOutputProps) {
  return (
    <section className="mb-6 overflow-hidden rounded-xl border border-border-dark bg-[#0d1117]">
      {/* Terminal header */}
      <div className="flex items-center justify-between border-b border-border-dark bg-surface-dark px-4 py-2">
        <span className="flex items-center gap-2 font-mono text-xs text-text-subtle">
          <span className="material-symbols-outlined text-[14px]">terminal</span>
          Pipeline Output
          {elapsed ? <span className="text-text-subtle/60">{elapsed}s</span> : null}
        </span>
        <div className="flex items-center gap-2">
          <span className={`inline-block h-2 w-2 rounded-full ${statusDotClass(status)}`} />
          <div className="flex gap-1.5">
            <div className="size-2.5 rounded-full bg-red-500/50" />
            <div className="size-2.5 rounded-full bg-yellow-500/50" />
            <div className="size-2.5 rounded-full bg-green-500/50" />
          </div>
        </div>
      </div>
      {/* Console body */}
      <pre className="custom-scrollbar max-h-[400px] overflow-y-auto whitespace-pre-wrap break-words p-4 font-mono text-xs leading-relaxed text-slate-400">
        {output || 'Listo. Selecciona un modo y haz click para ejecutar el pipeline.'}
      </pre>
    </section>
  );
}
