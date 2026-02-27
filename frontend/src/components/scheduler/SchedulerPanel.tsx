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
      return <span className="text-[10px] font-bold text-accent animate-pulse">publicando...</span>;
    case "error":
      return <span className="text-[10px] font-bold text-red">error</span>;
    case "pending":
      return <span className="text-[10px] font-bold text-orange">pendiente</span>;
    default:
      return <span className="text-[10px] font-bold text-dim">{status}</span>;
  }
}

function cardBorderColor(status: string, isToday: boolean): string {
  if (status === "completed") return "border-green/60";
  if (status === "error") return "border-red/60";
  if (status === "processing") return "border-accent/60";
  if (isToday) return "border-primary";
  return "border-border-dark";
}

interface AddPopoverProps {
  onAdd: (topic?: string) => void;
  onClose: () => void;
}

function AddPopover({ onAdd, onClose }: AddPopoverProps) {
  const [topic, setTopic] = useState("");

  return (
    <div
      className="fixed inset-0 z-30 flex items-center justify-center bg-black/40"
      onClick={onClose}
    >
      <div
        className="w-80 rounded-xl border border-border bg-card p-5 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <p className="mb-3 text-sm font-semibold">Añadir entrada</p>
        <input
          type="text"
          placeholder="Tema (vacío = auto-trending)"
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          className="mb-3 w-full rounded-md border border-border bg-code px-3 py-2 text-xs text-text outline-none focus:border-accent"
        />
        <div className="flex gap-2 justify-end">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg px-3 py-1.5 text-xs text-dim hover:text-text"
          >
            Cancelar
          </button>
          <button
            type="button"
            onClick={() => onAdd(topic.trim() || undefined)}
            className="rounded-lg bg-primary px-3 py-1.5 text-xs font-bold text-background-dark hover:bg-primary/90"
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
}

function CardPopover({ item, onRemove, onClose }: CardPopoverProps) {
  return (
    <div
      className="fixed inset-0 z-30 flex items-center justify-center bg-black/40"
      onClick={onClose}
    >
      <div
        className="w-72 rounded-xl border border-border bg-card p-5 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <p className="mb-1 text-sm font-semibold">{item.scheduled_date}</p>
        <p className="mb-1 text-xs text-dim">Tema: {item.topic || "AI auto-trending"}</p>
        <p className="mb-3 text-xs text-dim">Hora: {item.scheduled_time || "config default"}</p>
        {item.result_message && (
          <p className="mb-3 text-xs text-red/80 break-words">{item.result_message}</p>
        )}
        <div className="flex gap-2 justify-end">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg px-3 py-1.5 text-xs text-dim hover:text-text"
          >
            Cerrar
          </button>
          {item.status === "pending" && (
            <button
              type="button"
              onClick={onRemove}
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
  const { data, loading, saving, toggle, saveConfig, addItem, removeItem, autoFill } =
    useScheduler();
  const [configOpen, setConfigOpen] = useState(false);
  const [addDate, setAddDate] = useState<string | null>(null);
  const [popoverItem, setPopoverItem] = useState<QueueItem | null>(null);

  if (loading || !data) {
    return (
      <section className="rounded-xl border border-border-dark bg-secondary-dark p-5">
        <p className="text-sm text-dim animate-pulse">Cargando programador...</p>
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
    time: string | null;
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
    const dayCfg = config.schedule[dayName] || { enabled: false, time: null };
    const item = queue.find((q) => q.scheduled_date === dateStr);

    days.push({
      dateStr,
      dayName,
      dayLabel,
      dateLabel,
      item,
      enabled: dayCfg.enabled,
      time: item?.scheduled_time || dayCfg.time,
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

  return (
    <>
      <section className="rounded-xl border border-border-dark bg-secondary-dark p-5">
        {/* Header */}
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-bold text-white">Programador Automatico</h2>
            <p className="mt-0.5 text-xs text-text-subtle">
              Proximo: {formatNextRun(next_run)} &middot; Zona: {timezone}
            </p>
          </div>
          <button
            type="button"
            onClick={toggle}
            disabled={saving}
            className={`relative h-7 w-12 rounded-full transition-colors ${
              config.enabled ? "bg-green" : "bg-border-dark"
            }`}
          >
            <span
              className={`absolute top-1 h-5 w-5 rounded-full bg-white transition-transform ${
                config.enabled ? "translate-x-6" : "translate-x-1"
              }`}
            />
          </button>
        </div>

        {/* 7-day calendar cards */}
        <div className="mb-4 flex flex-wrap gap-2">
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
                className={`flex w-[110px] cursor-pointer flex-col items-center rounded-lg border-2 px-2 py-2.5 transition-colors hover:bg-surface-dark ${border} ${
                  isDisabled ? "opacity-40 cursor-default" : ""
                }`}
              >
                <span
                  className={`text-[11px] font-bold ${isToday ? "text-primary" : "text-text-subtle"}`}
                >
                  {day.dayLabel} {day.dateLabel}
                </span>
                {isDisabled ? (
                  <span className="mt-1 text-[10px] text-dim">descanso</span>
                ) : (
                  <>
                    <span className="mt-0.5 font-mono text-xs text-dim">{day.time || "--:--"}</span>
                    {item ? (
                      <>
                        <div className="mt-1">{statusBadge(item.status)}</div>
                        <span className="mt-0.5 max-w-full truncate text-center text-[10px] text-dim">
                          {item.topic || "AI auto"}
                        </span>
                      </>
                    ) : (
                      <span className="mt-1 text-[10px] text-dim/60">sin entrada</span>
                    )}
                  </>
                )}
              </div>
            );
          })}
        </div>

        {/* Action buttons */}
        <div className="flex flex-wrap gap-2">
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
            className="rounded-lg border border-border-dark bg-surface-dark px-3 py-1.5 text-xs font-semibold text-text-subtle transition hover:border-primary hover:text-white disabled:opacity-40"
          >
            + Añadir entrada
          </button>
          <button
            type="button"
            onClick={() => autoFill(7)}
            disabled={saving}
            className="rounded-lg border border-border-dark bg-surface-dark px-3 py-1.5 text-xs font-semibold text-text-subtle transition hover:border-primary hover:text-white disabled:opacity-40"
          >
            Auto-rellenar 7 dias
          </button>
          <button
            type="button"
            onClick={() => setConfigOpen(true)}
            className="rounded-lg border border-border-dark bg-surface-dark px-3 py-1.5 text-xs font-semibold text-text-subtle transition hover:border-primary hover:text-white"
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

      {addDate && <AddPopover onAdd={handleAddItem} onClose={() => setAddDate(null)} />}

      {popoverItem && (
        <CardPopover
          item={popoverItem}
          onRemove={() => handleRemoveItem(popoverItem.id)}
          onClose={() => setPopoverItem(null)}
        />
      )}
    </>
  );
}
