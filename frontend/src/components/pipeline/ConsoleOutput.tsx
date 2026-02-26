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
      return 'bg-green';
    case 'error':
      return 'bg-red';
    default:
      return 'bg-dim';
  }
}

export function ConsoleOutput({ status, elapsed, output }: ConsoleOutputProps) {
  return (
    <section className="mb-5 rounded-xl border border-border bg-card p-5">
      <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-dim">
        <span className={`inline-block h-2 w-2 rounded-full ${statusDotClass(status)}`} />
        Pipeline Output
        <span className="text-xs font-normal normal-case text-dim">
          {elapsed ? `${elapsed}s` : ''}
        </span>
      </h2>
      <pre className="max-h-[420px] overflow-y-auto whitespace-pre-wrap break-words rounded-lg border border-border bg-code p-4 font-mono text-xs leading-relaxed text-dim">
        {output}
      </pre>
    </section>
  );
}
