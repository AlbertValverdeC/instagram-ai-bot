import { useEffect, useState } from "react";

import type { DaySchedule, SchedulerConfig } from "../../types/scheduler";

const DAY_LABELS: Record<string, string> = {
  monday: "Lunes",
  tuesday: "Martes",
  wednesday: "Miércoles",
  thursday: "Jueves",
  friday: "Viernes",
  saturday: "Sábado",
  sunday: "Domingo",
};

const DAY_ORDER = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"];
const MIN_POSTS_PER_DAY = 1;
const MAX_POSTS_PER_DAY = 10;
const TIME_RE = /^([01]\d|2[0-3]):[0-5]\d$/;

interface ScheduleConfigModalProps {
  open: boolean;
  config: SchedulerConfig | null;
  onClose: () => void;
  onSave: (config: SchedulerConfig) => Promise<void>;
}

function nextTimeSlot(time: string, stepHours = 2): string {
  const hour = Number.parseInt(time.slice(0, 2), 10) || 8;
  const minute = Number.parseInt(time.slice(3, 5), 10) || 30;
  const nextHour = (hour + stepHours) % 24;
  return `${String(nextHour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
}

function normalizeTimes(times: unknown, fallbackTime: string, postsPerDay: number): string[] {
  const out: string[] = [];
  const source = Array.isArray(times) ? times : [];

  source.forEach((value) => {
    const slot = String(value || "").trim();
    if (!TIME_RE.test(slot)) return;
    if (out.includes(slot)) return;
    out.push(slot);
  });

  if (TIME_RE.test(fallbackTime) && !out.includes(fallbackTime)) {
    out.unshift(fallbackTime);
  }
  if (out.length === 0) {
    out.push("08:30");
  }

  while (out.length < postsPerDay) {
    let candidate = nextTimeSlot(out[out.length - 1], 2);
    for (let i = 0; i < 24 && out.includes(candidate); i++) {
      candidate = nextTimeSlot(candidate, 1);
    }
    if (out.includes(candidate)) break;
    out.push(candidate);
  }

  return out.slice(0, postsPerDay);
}

function normalizeDaySchedule(input: Partial<DaySchedule> | undefined): DaySchedule {
  const postsPerDayRaw = Number.parseInt(String(input?.posts_per_day ?? MIN_POSTS_PER_DAY), 10);
  const postsPerDay = Number.isFinite(postsPerDayRaw)
    ? Math.max(MIN_POSTS_PER_DAY, Math.min(MAX_POSTS_PER_DAY, postsPerDayRaw))
    : MIN_POSTS_PER_DAY;

  const fallbackTime =
    (typeof input?.time === "string" && TIME_RE.test(input.time) && input.time) ||
    (Array.isArray(input?.times) && typeof input?.times[0] === "string" && input.times[0]) ||
    "08:30";

  const times = normalizeTimes(input?.times, fallbackTime, postsPerDay);
  return {
    enabled: Boolean(input?.enabled),
    time: times[0] || null,
    posts_per_day: postsPerDay,
    times,
  };
}

export function ScheduleConfigModal({ open, config, onClose, onSave }: ScheduleConfigModalProps) {
  const [draft, setDraft] = useState<Record<string, DaySchedule>>({});
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ text: string; color: "green" | "red" } | null>(null);

  useEffect(() => {
    if (!open || !config) return;
    const normalizedDraft: Record<string, DaySchedule> = {};
    DAY_ORDER.forEach((day) => {
      normalizedDraft[day] = normalizeDaySchedule(config.schedule[day]);
    });
    setDraft(normalizedDraft);
    setMessage(null);
  }, [open, config]);

  const updateDay = (day: string, updater: (current: DaySchedule) => DaySchedule) => {
    setDraft((prev) => {
      const current = normalizeDaySchedule(prev[day]);
      const updated = normalizeDaySchedule(updater(current));
      return {
        ...prev,
        [day]: updated,
      };
    });
  };

  const handleSave = async () => {
    if (!config) return;
    setSaving(true);
    try {
      await onSave({ enabled: config.enabled, schedule: draft });
      setMessage({ text: "Horarios guardados", color: "green" });
      setTimeout(onClose, 600);
    } catch {
      setMessage({ text: "Error al guardar", color: "red" });
    } finally {
      setSaving(false);
    }
  };

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-black/60"
      onClick={onClose}
    >
      <div
        className="max-h-[90vh] w-[560px] max-w-[95vw] overflow-y-auto rounded-xl border border-border-dark bg-secondary-dark shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="sticky top-0 flex items-center justify-between border-b border-border-dark bg-secondary-dark px-6 py-5">
          <h2 className="font-display text-lg font-bold">Horarios por día</h2>
          <button
            type="button"
            onClick={onClose}
            className="text-2xl text-text-subtle transition hover:text-white"
          >
            ×
          </button>
        </div>

        <div className="space-y-3 px-6 py-5">
          {DAY_ORDER.map((day) => {
            const cfg = draft[day] || normalizeDaySchedule(undefined);
            return (
              <div
                key={day}
                className="rounded-lg border border-border-dark bg-surface-dark px-4 py-3"
              >
                <div className="flex flex-wrap items-center gap-3">
                  <button
                    type="button"
                    onClick={() =>
                      updateDay(day, (current) => ({ ...current, enabled: !current.enabled }))
                    }
                    className={`relative h-5 w-9 rounded-full transition-colors ${
                      cfg.enabled ? "bg-green" : "bg-border-dark"
                    }`}
                  >
                    <span
                      className={`absolute left-0.5 top-1/2 h-4 w-4 -translate-y-1/2 rounded-full bg-white transition-transform ${
                        cfg.enabled ? "translate-x-4" : "translate-x-0"
                      }`}
                    />
                  </button>

                  <span className="w-24 shrink-0 text-sm font-semibold">{DAY_LABELS[day]}</span>

                  <div className="flex items-center gap-2">
                    <span className="text-xs text-text-subtle">posts/día</span>
                    <input
                      type="number"
                      min={MIN_POSTS_PER_DAY}
                      max={MAX_POSTS_PER_DAY}
                      value={cfg.posts_per_day}
                      disabled={!cfg.enabled}
                      onChange={(e) => {
                        const parsed = Number.parseInt(e.target.value, 10);
                        const safe = Number.isFinite(parsed)
                          ? Math.max(MIN_POSTS_PER_DAY, Math.min(MAX_POSTS_PER_DAY, parsed))
                          : MIN_POSTS_PER_DAY;
                        updateDay(day, (current) => ({ ...current, posts_per_day: safe }));
                      }}
                      className="w-16 rounded-md border border-border-dark bg-background-dark px-2 py-1 text-xs text-slate-100 outline-none focus:border-primary disabled:opacity-30"
                    />
                  </div>
                </div>

                <div className="mt-3 grid gap-2 md:grid-cols-2">
                  {Array.from({ length: cfg.posts_per_day }).map((_, idx) => (
                    <label
                      key={`${day}-slot-${idx + 1}`}
                      className="flex items-center justify-between rounded-md border border-border-dark bg-background-dark px-2 py-1.5 text-xs"
                    >
                      <span className="text-text-subtle">Hora {idx + 1}</span>
                      <input
                        type="time"
                        value={cfg.times[idx] || ""}
                        disabled={!cfg.enabled}
                        onChange={(e) => {
                          const value = e.target.value || "08:30";
                          updateDay(day, (current) => {
                            const times = [...current.times];
                            times[idx] = value;
                            return { ...current, times, time: times[0] || null };
                          });
                        }}
                        className="rounded-md border border-border-dark bg-surface-dark px-2 py-1 font-mono text-xs text-slate-100 outline-none focus:border-primary disabled:opacity-30"
                      />
                    </label>
                  ))}
                </div>
              </div>
            );
          })}
        </div>

        <div className="sticky bottom-0 flex items-center justify-between border-t border-border-dark bg-secondary-dark px-6 py-4">
          <span className={`text-sm ${message?.color === "green" ? "text-green" : "text-red"}`}>
            {message?.text || ""}
          </span>
          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            data-loading={saving ? "true" : undefined}
            className="btn-success px-4 py-2"
          >
            {saving ? "Guardando..." : "Guardar"}
          </button>
        </div>
      </div>
    </div>
  );
}
