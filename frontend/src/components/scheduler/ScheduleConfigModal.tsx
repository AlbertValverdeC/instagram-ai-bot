import { useEffect, useState } from 'react';

import type { SchedulerConfig, DaySchedule } from '../../types/scheduler';

const DAY_LABELS: Record<string, string> = {
  monday: 'Lunes',
  tuesday: 'Martes',
  wednesday: 'Miércoles',
  thursday: 'Jueves',
  friday: 'Viernes',
  saturday: 'Sábado',
  sunday: 'Domingo',
};

const DAY_ORDER = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'];

interface ScheduleConfigModalProps {
  open: boolean;
  config: SchedulerConfig | null;
  onClose: () => void;
  onSave: (config: SchedulerConfig) => Promise<void>;
}

export function ScheduleConfigModal({ open, config, onClose, onSave }: ScheduleConfigModalProps) {
  const [draft, setDraft] = useState<Record<string, DaySchedule>>({});
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ text: string; color: 'green' | 'red' } | null>(null);

  useEffect(() => {
    if (!open || !config) return;
    setDraft({ ...config.schedule });
    setMessage(null);
  }, [open, config]);

  const updateDay = (day: string, field: 'enabled' | 'time', value: boolean | string | null) => {
    setDraft((prev) => ({
      ...prev,
      [day]: {
        ...prev[day],
        [field]: value,
      },
    }));
  };

  const handleSave = async () => {
    if (!config) return;
    setSaving(true);
    try {
      await onSave({ enabled: config.enabled, schedule: draft });
      setMessage({ text: 'Horarios guardados', color: 'green' });
      setTimeout(onClose, 600);
    } catch {
      setMessage({ text: 'Error al guardar', color: 'red' });
    } finally {
      setSaving(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div
        className="max-h-[90vh] w-[500px] max-w-[95vw] overflow-y-auto rounded-xl border border-border bg-card shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="sticky top-0 flex items-center justify-between border-b border-border bg-card px-6 py-5">
          <h2 className="text-lg font-bold">Horarios por dia</h2>
          <button type="button" onClick={onClose} className="text-2xl text-dim transition hover:text-text">
            ×
          </button>
        </div>

        <div className="px-6 py-5 space-y-3">
          {DAY_ORDER.map((day) => {
            const cfg = draft[day] || { enabled: false, time: null };
            return (
              <div key={day} className="flex items-center gap-4 rounded-lg border border-border bg-code px-4 py-3">
                <button
                  type="button"
                  onClick={() => updateDay(day, 'enabled', !cfg.enabled)}
                  className={`h-5 w-9 rounded-full transition-colors ${
                    cfg.enabled ? 'bg-green' : 'bg-border'
                  } relative`}
                >
                  <span
                    className={`absolute top-0.5 h-4 w-4 rounded-full bg-white transition-transform ${
                      cfg.enabled ? 'translate-x-4' : 'translate-x-0.5'
                    }`}
                  />
                </button>
                <span className="w-24 text-sm font-semibold">{DAY_LABELS[day]}</span>
                <input
                  type="time"
                  value={cfg.time || ''}
                  disabled={!cfg.enabled}
                  onChange={(e) => updateDay(day, 'time', e.target.value || null)}
                  className="rounded-md border border-border bg-bg px-2 py-1 font-mono text-xs text-text outline-none focus:border-accent disabled:opacity-30"
                />
              </div>
            );
          })}
        </div>

        <div className="sticky bottom-0 flex items-center justify-between border-t border-border bg-card px-6 py-4">
          <span className={`text-sm ${message?.color === 'green' ? 'text-green' : 'text-red'}`}>
            {message?.text || ''}
          </span>
          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            className="rounded-lg border border-green bg-green/10 px-4 py-2 text-sm font-semibold text-green transition hover:bg-green/20 disabled:opacity-40"
          >
            {saving ? 'Guardando...' : 'Guardar'}
          </button>
        </div>
      </div>
    </div>
  );
}
