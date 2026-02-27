import { useState } from "react";

import { useScheduler } from "../../hooks/useScheduler";
import { ScheduleConfigModal } from "./ScheduleConfigModal";
import type { QueueItem } from "../../types/scheduler";

const DAY_LABELS_SHORT: Record<string, string> = {
  monday: "Lun",
  tuesday: "Mar",
  wednesday: "Mié",
  thursday: "Jue",
  friday: "Vie",
  saturday: "Sáb",
  sunday: "Dom",
};

const DAY_NAMES = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"];

function formatNextRun(
  next: { day_name: string; date: string; time: string; hours_until: number } | null,
): string {
  if (!next) return "Sin publicaciones pendientes";
  const dayLabel = DAY_LABELS_SHORT[next.day_name] || next.day_name;
  const d = next.date.slice(5); // MM-DD
  const h = next.hours_until;
  const hStr = h < 1 ? "<1h" : h < 24 ? `${Math.round(h)}h` : `${Math.round(h / 24)}d`;
  return `${dayLabel} ${d} ${next.time} (en ${hStr})`;
}

function statusBadge(status: string) {
  switch (status) {
    case "completed":
      return <span className="text-[10px] font-bold text-green">completado</span>;
    case "processing":
      return (
        <span className="text-[10px] font-bold text-primary animate-pulse">publicando...</span>
      );
    case "error":
      return <span className="text-[10px] font-bold text-red">error</span>;
    case "pending":
      return <span className="text-[10px] font-bold text-orange">pendiente</span>;
    default:
      return <span className="text-[10px] font-bold text-text-subtle">{status}</span>;
  }
}

function cardBorderColor(status: string, isToday: boolean): string {
  if (status === "completed") return "border-green/60";
  if (status === "error") return "border-red/60";
  if (status === "processing") return "border-primary/60";
  if (isToday) return "border-primary";
  return "border-border-dark";
}

interface AddPopoverProps {
  onAdd: (topic?: string) => void;
  onClose: () => void;
  saving: boolean;
}

function AddPopover({ onAdd, onClose, saving }: AddPopoverProps) {
  const [topic, setTopic] = useState("");

  return (
    <div
      className="fixed inset-0 z-30 flex items-center justify-center bg-black/40"
      onClick={onClose}
    >
      <div
        className="w-[92vw] max-w-sm rounded-xl border border-border-dark bg-secondary-dark p-5 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <p className="mb-3 text-sm font-semibold">Añadir entrada</p>
        <input
          type="text"
          placeholder="Tema (vacío = auto-trending)"
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          className="mb-3 w-full rounded-md border border-border-dark bg-surface-dark px-3 py-2 text-xs text-slate-100 outline-none focus:border-primary focus:ring-1 focus:ring-primary"
        />
        <div className="flex gap-2 justify-end">
          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            className="btn-ghost rounded-lg px-3 py-1.5 text-xs"
          >
            Cancelar
          </button>
          <button
            type="button"
            onClick={() => onAdd(topic.trim() || undefined)}
            disabled={saving}
            data-loading={saving ? "true" : undefined}
            className="btn-primary rounded-lg px-3 py-1.5 text-xs"
          >
            Añadir
          </button>
        </div>
      </div>
    </div>
  );
}

interface CardPopoverProps {
  item: QueueItem;
  onRemove: () => void;
  onClose: () => void;
  saving: boolean;
}

function CardPopover({ item, onRemove, onClose, saving }: CardPopoverProps) {
  const progressLabel =
    item.runs_total > 1
      ? `${Math.min(item.runs_completed, item.runs_total)}/${item.runs_total}`
      : null;
  const messageClass = item.status === "error" ? "text-red/80" : "text-text-subtle";
  return (
    <div
      className="fixed inset-0 z-30 flex items-center justify-center bg-black/40"
      onClick={onClose}
    >
      <div
        className="w-[92vw] max-w-sm rounded-xl border border-border-dark bg-secondary-dark p-5 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <p className="mb-1 text-sm font-semibold">{item.scheduled_date}</p>
        <p className="mb-1 text-xs text-text-subtle">Tema: {item.topic || "AI auto-trending"}</p>
        <p className="mb-3 text-xs text-text-subtle">
          Hora: {item.scheduled_time || "config default"}
        </p>
        {progressLabel && (
          <p className="mb-2 text-xs text-text-subtle">Progreso: {progressLabel}</p>
        )}
        {item.result_message && (
          <p className={`mb-3 text-xs break-words ${messageClass}`}>{item.result_message}</p>
        )}
        <div className="flex gap-2 justify-end">
          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            className="btn-ghost rounded-lg px-3 py-1.5 text-xs"
          >
            Cerrar
          </button>
          {item.status === "pending" && (
            <button
              type="button"
              onClick={onRemove}
              disabled={saving}
              data-loading={saving ? "true" : undefined}
              className="rounded-lg border border-red bg-red/10 px-3 py-1.5 text-xs font-semibold text-red hover:bg-red/20"
            >
              Eliminar
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export function SchedulerPanel() {
  const {
    data,
    loading,
    saving,
    error,
    toggle,
    saveConfig,
    addItem,
    removeItem,
    autoFill,
    refresh,
  } = useScheduler();
  const [configOpen, setConfigOpen] = useState(false);
  const [addDate, setAddDate] = useState<string | null>(null);
  const [popoverItem, setPopoverItem] = useState<QueueItem | null>(null);

  if (loading) {
    return (
      <section className="rounded-xl border border-border-dark bg-secondary-dark p-5">
        <p className="text-sm text-text-subtle animate-pulse">Cargando programador...</p>
      </section>
    );
  }

  if (!data) {
    return (
      <section className="rounded-xl border border-red/40 bg-secondary-dark p-5">
        <p className="text-sm font-semibold text-red">
          {error || "No se pudo cargar el programador."}
        </p>
        <button
          type="button"
          onClick={() => void refresh()}
          data-loading={loading ? "true" : undefined}
          className="mt-3 rounded-lg border border-border-dark bg-surface-dark px-3 py-1.5 text-xs font-semibold text-text-subtle transition hover:border-primary hover:text-white"
        >
          Reintentar
        </button>
      </section>
    );
  }

  const { config, queue, next_run, timezone } = data;

  // Build 7-day calendar starting from today
  const today = new Date();
  const todayStr = today.toISOString().slice(0, 10);
  const days: Array<{
    dateStr: string;
    dayName: string;
    dayLabel: string;
    dateLabel: string;
    item: QueueItem | undefined;
    enabled: boolean;
    timeSummary: string | null;
    postsPerDay: number;
  }> = [];

  for (let i = 0; i < 7; i++) {
    const d = new Date(today);
    d.setDate(d.getDate() + i);
    const dateStr = d.toISOString().slice(0, 10);
    const jsDay = d.getDay(); // 0=Sun
    const dayIdx = jsDay === 0 ? 6 : jsDay - 1; // Convert to Mon=0
    const dayName = DAY_NAMES[dayIdx];
    const dayLabel = DAY_LABELS_SHORT[dayName];
    const dd = d.getDate();
    const monthNames = [
      "ene",
      "feb",
      "mar",
      "abr",
      "may",
      "jun",
      "jul",
      "ago",
      "sep",
      "oct",
      "nov",
      "dic",
    ];
    const dateLabel = `${dd} ${monthNames[d.getMonth()]}`;
    const dayCfg = config.schedule[dayName] || {
      enabled: false,
      time: null,
      posts_per_day: 1,
      times: [],
    };
    const item = queue.find((q) => q.scheduled_date === dateStr);
    const times = Array.isArray(dayCfg.times)
      ? dayCfg.times.filter((t) => typeof t === "string" && t)
      : [];
    const firstTime = item?.scheduled_time || times[0] || dayCfg.time;
    const timeSummary =
      times.length > 1 && !item?.scheduled_time
        ? `${firstTime || "--:--"} +${times.length - 1}`
        : firstTime;

    days.push({
      dateStr,
      dayName,
      dayLabel,
      dateLabel,
      item,
      enabled: dayCfg.enabled,
      timeSummary,
      postsPerDay: Number(dayCfg.posts_per_day || 1),
    });
  }

  const handleAddItem = async (topic?: string) => {
    if (!addDate) return;
    await addItem(addDate, topic);
    setAddDate(null);
  };

  const handleRemoveItem = async (id: number) => {
    await removeItem(id);
    setPopoverItem(null);
  };

  const enabledDays = days.filter((d) => d.enabled).length;
  const queuedDays = days.filter((d) => Boolean(d.item)).length;
  const pendingItems = queue.filter((q) => q.status === "pending").length;

  return (
    <>
      <section className="rounded-xl border border-border-dark bg-secondary-dark p-4 sm:p-5">
        {/* Header */}
        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0">
            <h2 className="font-display text-base font-bold text-white sm:text-sm">
              Programador Automatico
            </h2>
            <p className="mt-0.5 text-xs leading-relaxed text-text-subtle">
              Próximo: {formatNextRun(next_run)}
            </p>
            <p className="text-[11px] text-text-subtle/80">Zona: {timezone}</p>
          </div>
          <button
            type="button"
            aria-label={config.enabled ? "Desactivar programador" : "Activar programador"}
            onClick={toggle}
            disabled={saving}
            data-loading={saving ? "true" : undefined}
            className={`relative h-8 w-14 self-start rounded-full border transition-all sm:self-auto ${
              config.enabled
                ? "border-green/80 bg-green/90 shadow-[0_0_0_3px_rgba(16,185,129,0.2)]"
                : "border-border-dark bg-border-dark"
            }`}
          >
            <span
              className={`absolute left-1 top-1/2 h-6 w-6 -translate-y-1/2 rounded-full bg-white transition-transform ${
                config.enabled ? "translate-x-6" : "translate-x-0"
              }`}
            />
          </button>
        </div>

        <div className="mb-4 grid grid-cols-3 gap-2">
          <div className="rounded-lg border border-border-dark bg-surface-dark/50 px-2.5 py-2">
            <p className="text-[10px] uppercase tracking-wide text-text-subtle">Días activos</p>
            <p className="text-sm font-semibold text-white">{enabledDays}/7</p>
          </div>
          <div className="rounded-lg border border-border-dark bg-surface-dark/50 px-2.5 py-2">
            <p className="text-[10px] uppercase tracking-wide text-text-subtle">Con entrada</p>
            <p className="text-sm font-semibold text-white">{queuedDays}/7</p>
          </div>
          <div className="rounded-lg border border-border-dark bg-surface-dark/50 px-2.5 py-2">
            <p className="text-[10px] uppercase tracking-wide text-text-subtle">Pendientes</p>
            <p className="text-sm font-semibold text-white">{pendingItems}</p>
          </div>
        </div>

        {/* 7-day calendar cards */}
        <div className="mb-4 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
          {days.map((day) => {
            const isToday = day.dateStr === todayStr;
            const isDisabled = !day.enabled;
            const item = day.item;
            const border = isDisabled
              ? "border-border-dark/40"
              : cardBorderColor(item?.status || "", isToday);

            return (
              <div
                key={day.dateStr}
                onClick={() => {
                  if (isDisabled) return;
                  if (item) {
                    setPopoverItem(item);
                  } else {
                    setAddDate(day.dateStr);
                  }
                }}
                className={`flex min-h-[106px] w-full cursor-pointer flex-col rounded-lg border-2 px-3 py-2.5 transition-colors hover:bg-surface-dark ${border} ${
                  isDisabled ? "opacity-40 cursor-default" : ""
                }`}
              >
                <div className="flex w-full items-start justify-between gap-2">
                  <span
                    className={`text-[11px] font-bold ${isToday ? "text-primary" : "text-text-subtle"}`}
                  >
                    {day.dayLabel} {day.dateLabel}
                  </span>
                  {!isDisabled && (
                    <span className="rounded-full border border-border-dark px-1.5 py-0.5 text-[9px] font-semibold text-text-subtle/80">
                      {day.postsPerDay}/día
                    </span>
                  )}
                </div>
                {isDisabled ? (
                  <span className="mt-3 text-[10px] text-text-subtle">descanso</span>
                ) : (
                  <>
                    <span className="mt-1.5 font-mono text-sm text-slate-100">
                      {day.timeSummary || "--:--"}
                    </span>
                    {item ? (
                      <>
                        <div className="mt-1.5">{statusBadge(item.status)}</div>
                        {item.runs_total > 1 && (
                          <span className="mt-0.5 text-[10px] text-text-subtle/70">
                            {Math.min(item.runs_completed, item.runs_total)}/{item.runs_total}
                          </span>
                        )}
                        <span className="mt-0.5 max-w-full truncate text-[10px] text-text-subtle">
                          {item.topic || "AI auto"}
                        </span>
                      </>
                    ) : (
                      <span className="mt-1.5 text-[10px] text-text-subtle/60">
                        sin entrada (tap para añadir)
                      </span>
                    )}
                  </>
                )}
              </div>
            );
          })}
        </div>

        {/* Action buttons */}
        <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
          <button
            type="button"
            onClick={() => {
              // Find next empty enabled date
              const emptyDay = days.find((d) => d.enabled && !d.item);
              if (emptyDay) {
                setAddDate(emptyDay.dateStr);
              }
            }}
            disabled={saving}
            data-loading={saving ? "true" : undefined}
            className="w-full rounded-lg border border-border-dark bg-surface-dark px-3 py-2 text-xs font-semibold text-text-subtle transition hover:border-primary hover:text-white disabled:opacity-40 sm:w-auto sm:py-1.5"
          >
            + Añadir entrada
          </button>
          <button
            type="button"
            onClick={() => autoFill(7)}
            disabled={saving}
            data-loading={saving ? "true" : undefined}
            className="w-full rounded-lg border border-border-dark bg-surface-dark px-3 py-2 text-xs font-semibold text-text-subtle transition hover:border-primary hover:text-white disabled:opacity-40 sm:w-auto sm:py-1.5"
          >
            Auto-rellenar 7 días
          </button>
          <button
            type="button"
            onClick={() => setConfigOpen(true)}
            data-loading={saving ? "true" : undefined}
            className="w-full rounded-lg border border-border-dark bg-surface-dark px-3 py-2 text-xs font-semibold text-text-subtle transition hover:border-primary hover:text-white sm:w-auto sm:py-1.5"
          >
            Horarios
          </button>
        </div>
      </section>

      <ScheduleConfigModal
        open={configOpen}
        config={config}
        onClose={() => setConfigOpen(false)}
        onSave={saveConfig}
      />

      {addDate && <AddPopover onAdd={handleAddItem} onClose={() => setAddDate(null)} saving={saving} />}

      {popoverItem && (
        <CardPopover
          item={popoverItem}
          onRemove={() => handleRemoveItem(popoverItem.id)}
          onClose={() => setPopoverItem(null)}
          saving={saving}
        />
      )}
    </>
  );
}
