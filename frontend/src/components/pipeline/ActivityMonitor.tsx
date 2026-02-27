import { useEffect, useRef, useState } from "react";

import type { ActivityEntry } from "../../types/activity";

/* ------------------------------------------------------------------ */
/*  Props                                                              */
/* ------------------------------------------------------------------ */

interface ActivityMonitorProps {
  entries: ActivityEntry[];
  activeOperation: { level: number; label: string; startedAt: number } | null;
  e2eRawOutput: string;
  onClear: () => void;
}

/* ------------------------------------------------------------------ */
/*  Sub-components                                                     */
/* ------------------------------------------------------------------ */

function ProgressBar({
  activeOperation,
}: {
  activeOperation: ActivityMonitorProps["activeOperation"];
}) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!activeOperation) {
      setElapsed(0);
      return;
    }
    setElapsed(Math.floor((Date.now() - activeOperation.startedAt) / 1000));
    const interval = setInterval(() => {
      setElapsed(Math.floor((Date.now() - activeOperation.startedAt) / 1000));
    }, 1000);
    return () => clearInterval(interval);
  }, [activeOperation]);

  if (!activeOperation) return null;

  return (
    <div className="border-b border-border-dark px-4 py-3">
      <div className="mb-1.5 flex items-center justify-between text-xs">
        <span className="font-semibold text-orange">
          Nivel {activeOperation.level} en curso: {activeOperation.label}
        </span>
        <span className="font-mono text-text-subtle">{elapsed}s</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-surface-dark">
        <div className="animate-progress h-full w-1/3 rounded-full bg-orange" />
      </div>
    </div>
  );
}

function statusDotClass(status: ActivityEntry["status"]): string {
  switch (status) {
    case "running":
      return "bg-orange animate-pulse";
    case "success":
      return "bg-emerald-500";
    case "error":
      return "bg-red";
    default:
      return "bg-text-subtle/50";
  }
}

function levelBadgeClass(level: ActivityEntry["level"]): string {
  switch (level) {
    case 1:
      return "bg-sky-400/15 text-sky-300 border-sky-400/30";
    case 2:
      return "bg-violet-400/15 text-violet-300 border-violet-400/30";
    case 3:
      return "bg-emerald-400/15 text-emerald-300 border-emerald-400/30";
    case 4:
      return "bg-orange/15 text-orange border-orange/30";
    default:
      return "bg-text-subtle/10 text-text-subtle border-text-subtle/20";
  }
}

function formatTime(date: Date): string {
  return date.toLocaleTimeString("es-ES", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function ActivityEntryRow({ entry }: { entry: ActivityEntry }) {
  return (
    <div className="flex items-start gap-3 px-4 py-1.5 text-xs transition-colors hover:bg-surface-dark/30">
      <span className="shrink-0 font-mono text-text-subtle/60">{formatTime(entry.timestamp)}</span>
      <span
        className={`mt-1 inline-block size-2 shrink-0 rounded-full ${statusDotClass(entry.status)}`}
      />
      {entry.level && (
        <span
          className={`shrink-0 rounded border px-1.5 py-0.5 text-[10px] font-bold leading-none ${levelBadgeClass(entry.level)}`}
        >
          N{entry.level}
        </span>
      )}
      <span className={`${entry.status === "error" ? "text-red" : "text-slate-300"}`}>
        {entry.message}
      </span>
    </div>
  );
}

function CollapsibleRawOutput({ output }: { output: string }) {
  const [open, setOpen] = useState(false);

  if (!output) return null;

  return (
    <div className="border-t border-border-dark">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 px-4 py-2.5 text-xs font-semibold text-text-subtle transition-colors hover:bg-surface-dark/30 hover:text-white"
      >
        <span
          className="material-symbols-outlined text-[14px] transition-transform"
          style={{ transform: open ? "rotate(90deg)" : "rotate(0deg)" }}
        >
          play_arrow
        </span>
        Output completo del pipeline
      </button>
      {open && (
        <pre className="custom-scrollbar max-h-[300px] overflow-y-auto whitespace-pre-wrap break-words bg-[#0d1117] px-4 py-3 font-mono text-xs leading-relaxed text-slate-400">
          {output}
        </pre>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main component                                                     */
/* ------------------------------------------------------------------ */

function globalStatusDot(
  entries: ActivityEntry[],
  activeOperation: ActivityMonitorProps["activeOperation"],
): string {
  if (activeOperation) return "bg-orange animate-pulse";
  if (entries.length === 0) return "bg-text-subtle/50";
  const last = entries[entries.length - 1];
  if (last.status === "error") return "bg-red";
  if (last.status === "success") return "bg-emerald-500";
  return "bg-text-subtle/50";
}

export function ActivityMonitor({
  entries,
  activeOperation,
  e2eRawOutput,
  onClear,
}: ActivityMonitorProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) {
      el.scrollTop = el.scrollHeight;
    }
  }, [entries]);

  return (
    <section className="overflow-hidden rounded-xl border border-border-dark bg-secondary-dark shadow-lg">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border-dark bg-surface-dark/50 px-4 py-3">
        <h2 className="flex items-center gap-2 text-sm font-bold text-white">
          <span className="material-symbols-outlined text-primary text-[18px]">monitor_heart</span>
          Monitor de Actividad
        </h2>
        <div className="flex items-center gap-3">
          {entries.length > 0 && (
            <button
              type="button"
              onClick={onClear}
              className="rounded-md px-2.5 py-1 text-[11px] font-semibold text-text-subtle transition-colors hover:bg-surface-dark hover:text-white"
            >
              Limpiar
            </button>
          )}
          <span
            className={`inline-block size-2.5 rounded-full ${globalStatusDot(entries, activeOperation)}`}
          />
        </div>
      </div>

      {/* Progress bar */}
      <ProgressBar activeOperation={activeOperation} />

      {/* Entries */}
      <div ref={scrollRef} className="custom-scrollbar max-h-[260px] overflow-y-auto py-2">
        {entries.length === 0 ? (
          <p className="px-4 py-6 text-center text-xs italic text-text-subtle">
            Sin actividad aún. Ejecuta una operación para ver el progreso aquí.
          </p>
        ) : (
          entries.map((entry) => <ActivityEntryRow key={entry.id} entry={entry} />)
        )}
      </div>

      {/* Collapsible raw output */}
      <CollapsibleRawOutput output={e2eRawOutput} />
    </section>
  );
}
