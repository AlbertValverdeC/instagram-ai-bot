import { useEffect, useMemo, useState } from "react";

import { apiClient } from "../../api/client";
import type { ApiKeyItem } from "../../types";

interface KeysModalProps {
  open: boolean;
  onClose: () => void;
}

export function KeysModal({ open, onClose }: KeysModalProps) {
  const [items, setItems] = useState<ApiKeyItem[]>([]);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{
    text: string;
    color: "green" | "red" | "orange";
  } | null>(null);

  useEffect(() => {
    if (!open) {
      return;
    }

    (async () => {
      try {
        const data = await apiClient.getKeys();
        setItems(data);
        const values: Record<string, string> = {};
        data.forEach((item) => {
          values[item.key] = item.secret ? "" : item.value;
        });
        setDraft(values);
      } catch {
        setMessage({ text: "Error cargando API keys.", color: "red" });
      }
    })();
  }, [open]);

  const grouped = useMemo(() => {
    const groups = new Map<string, ApiKeyItem[]>();
    items.forEach((item) => {
      const list = groups.get(item.group) || [];
      list.push(item);
      groups.set(item.group, list);
    });
    return Array.from(groups.entries());
  }, [items]);

  const save = async () => {
    const payload: Record<string, string> = {};
    items.forEach((item) => {
      const value = (draft[item.key] || "").trim();
      if (value && !value.startsWith("***")) {
        payload[item.key] = value;
      }
    });

    if (Object.keys(payload).length === 0) {
      setMessage({ text: "No hay cambios para guardar", color: "orange" });
      return;
    }

    try {
      setSaving(true);
      const result = await apiClient.saveKeys(payload);
      setMessage({ text: `Guardado: ${result.saved} clave(s) actualizadas`, color: "green" });
      const data = await apiClient.getKeys();
      setItems(data);
      const values: Record<string, string> = {};
      data.forEach((item) => {
        values[item.key] = item.secret ? "" : item.value;
      });
      setDraft(values);
    } catch {
      setMessage({ text: "Error al guardar", color: "red" });
    } finally {
      setSaving(false);
    }
  };

  if (!open) {
    return null;
  }

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-black/60"
      onClick={onClose}
    >
      <div
        className="max-h-[90vh] w-[700px] max-w-[95vw] overflow-y-auto rounded-xl border border-border-dark bg-secondary-dark shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="sticky top-0 flex items-center justify-between border-b border-border-dark bg-secondary-dark px-6 py-5">
          <h2 className="font-display text-lg font-bold">🔑 API Keys</h2>
          <button
            type="button"
            onClick={onClose}
            className="text-2xl text-text-subtle transition hover:text-white"
          >
            ×
          </button>
        </div>

        <div className="px-6 py-5">
          {grouped.length === 0 ? (
            <p className="text-sm italic text-text-subtle">Cargando...</p>
          ) : (
            grouped.map(([group, groupItems]) => (
              <div key={group} className="mb-5">
                <h3 className="mb-2 border-b border-border-dark pb-1 text-[11px] font-bold uppercase tracking-[1px] text-primary">
                  {group}
                </h3>
                <div className="space-y-4">
                  {groupItems.map((item) => (
                    <div key={item.key}>
                      <div className="mb-1 flex items-center gap-2 text-sm font-semibold">
                        <span
                          className={`inline-block h-1.5 w-1.5 rounded-full ${
                            item.configured
                              ? "bg-green"
                              : item.required
                                ? "bg-red"
                                : "bg-text-subtle"
                          }`}
                        />
                        <span>{item.label}</span>
                        {item.required ? (
                          <span className="text-[10px] font-bold text-red">REQUERIDA</span>
                        ) : null}
                        {item.url ? (
                          <a
                            href={item.url}
                            target="_blank"
                            rel="noreferrer"
                            className="ml-auto text-xs text-primary/80 underline-offset-2 hover:underline"
                          >
                            Obtener →
                          </a>
                        ) : null}
                      </div>
                      <p className="mb-1 text-xs text-text-subtle">{item.hint}</p>
                      <input
                        type={item.secret ? "password" : "text"}
                        placeholder={item.configured && item.secret ? item.value : item.placeholder}
                        value={draft[item.key] ?? ""}
                        onChange={(e) =>
                          setDraft((prev) => ({ ...prev, [item.key]: e.target.value }))
                        }
                        className="w-full rounded-md border border-border-dark bg-surface-dark px-3 py-2 font-mono text-xs text-slate-100 outline-none focus:border-primary"
                      />
                    </div>
                  ))}
                </div>
              </div>
            ))
          )}
        </div>

        <div className="sticky bottom-0 flex items-center justify-between border-t border-border-dark bg-secondary-dark px-6 py-4">
          <span
            className={`text-sm ${
              message?.color === "green"
                ? "text-green"
                : message?.color === "red"
                  ? "text-red"
                  : "text-orange"
            }`}
          >
            {message?.text || ""}
          </span>
          <button
            type="button"
            onClick={save}
            disabled={saving}
            data-loading={saving ? "true" : undefined}
            className="btn-success px-4 py-2"
          >
            {saving ? "Guardando..." : "💾 Guardar en .env"}
          </button>
        </div>
      </div>
    </div>
  );
}
