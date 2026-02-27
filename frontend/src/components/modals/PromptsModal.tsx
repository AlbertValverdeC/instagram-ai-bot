import { useEffect, useMemo, useState } from "react";

import { apiClient } from "../../api/client";
import type { PromptItem } from "../../types";

interface PromptsModalProps {
  open: boolean;
  onClose: () => void;
}

function riskLabelClass(risk?: string): string {
  switch (risk) {
    case "alto":
      return "rounded-full border border-red/40 bg-red/20 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-red";
    case "medio-alto":
      return "rounded-full border border-orange/40 bg-orange/20 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-orange";
    case "medio":
      return "rounded-full border border-yellow-400/40 bg-yellow-400/20 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-yellow-400";
    default:
      return "rounded-full border border-dim/40 bg-dim/20 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-dim";
  }
}

export function PromptsModal({ open, onClose }: PromptsModalProps) {
  const [prompts, setPrompts] = useState<PromptItem[]>([]);
  const [activeCategory, setActiveCategory] = useState<string>("");
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [messageById, setMessageById] = useState<
    Record<string, { text: string; type: "ok" | "err" }>
  >({});

  useEffect(() => {
    if (!open) {
      return;
    }

    (async () => {
      try {
        const data = await apiClient.getPrompts();
        setPrompts(data);
        const categories = Array.from(new Set(data.map((item) => item.category)));
        setActiveCategory((prev) => prev || categories[0] || "");
        const draftValues: Record<string, string> = {};
        data.forEach((item) => {
          draftValues[item.id] = item.text;
        });
        setDraft(draftValues);
      } catch {
        setPrompts([]);
      }
    })();
  }, [open]);

  const categories = useMemo(
    () => Array.from(new Set(prompts.map((item) => item.category))),
    [prompts],
  );
  const visiblePrompts = useMemo(
    () => prompts.filter((item) => item.category === activeCategory),
    [prompts, activeCategory],
  );

  const showMessage = (id: string, text: string, type: "ok" | "err") => {
    setMessageById((prev) => ({ ...prev, [id]: { text, type } }));
    window.setTimeout(() => {
      setMessageById((prev) => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
    }, 3000);
  };

  const savePrompt = async (id: string) => {
    const text = draft[id] ?? "";
    try {
      await apiClient.savePrompt(id, text);
      showMessage(id, "Guardado correctamente", "ok");
      const data = await apiClient.getPrompts();
      setPrompts(data);
    } catch (error) {
      const err = error as Error;
      showMessage(id, err.message || "Error al guardar", "err");
    }
  };

  const resetPrompt = async (id: string) => {
    if (
      !window.confirm(
        "¿Restaurar este prompt al texto original?\nSe perderán los cambios personalizados.",
      )
    ) {
      return;
    }

    try {
      await apiClient.resetPrompt(id);
      showMessage(id, "Restaurado al original", "ok");
      const data = await apiClient.getPrompts();
      setPrompts(data);
      const draftValues: Record<string, string> = {};
      data.forEach((item) => {
        draftValues[item.id] = item.text;
      });
      setDraft(draftValues);
    } catch (error) {
      const err = error as Error;
      showMessage(id, err.message || "Error al restaurar", "err");
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
        className="max-h-[90vh] w-[900px] max-w-[95vw] overflow-y-auto rounded-xl border border-border bg-card shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-border bg-card px-6 py-5">
          <h2 className="text-lg font-bold">✏️ Editor de Prompts</h2>
          <button
            type="button"
            onClick={onClose}
            className="text-2xl text-dim transition hover:text-text"
          >
            ×
          </button>
        </div>

        <div className="sticky top-[69px] z-10 flex border-b border-border bg-card px-6">
          {categories.map((category) => (
            <button
              key={category}
              type="button"
              onClick={() => setActiveCategory(category)}
              className={`border-b-2 px-4 py-3 text-sm font-semibold transition ${
                category === activeCategory
                  ? "border-accent text-accent"
                  : "border-transparent text-dim hover:text-text"
              }`}
            >
              {category}
            </button>
          ))}
        </div>

        <div className="px-6 py-5">
          <div className="mb-4 rounded-lg border border-accent/20 bg-accent/5 p-3 text-xs text-dim">
            Este panel cambia el comportamiento real del pipeline. Antes de editar, revisa{" "}
            <b>Qué hace</b>, <b>Cuándo se usa</b> y <b>Si lo cambias</b>. Las llaves dobles{" "}
            <code>{"{{ }}"}</code> son literales. Las llaves simples <code>{"{variable}"}</code> se
            reemplazan con datos reales en ejecución.
          </div>

          {visiblePrompts.map((prompt) => {
            const msg = messageById[prompt.id];
            return (
              <article key={prompt.id} className="mb-4 rounded-xl border border-border bg-code p-4">
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <h3 className="text-sm font-bold">{prompt.name}</h3>
                  <span
                    className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${
                      prompt.type === "meta"
                        ? "bg-purple/20 text-purple"
                        : "bg-orange/20 text-orange"
                    }`}
                  >
                    {prompt.type}
                  </span>
                  {prompt.custom ? (
                    <span className="rounded-full bg-green/20 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-green">
                      Personalizado
                    </span>
                  ) : null}
                  <span className="text-xs text-dim">{prompt.module}</span>
                </div>

                <p className="mb-3 text-xs text-dim">{prompt.description}</p>

                <div className="mb-3 space-y-1 rounded-lg border border-border bg-white/5 p-3 text-xs text-text">
                  <p>
                    <span className="font-bold text-accent">Qué hace:</span>{" "}
                    {prompt.what_it_does || "Sin descripción"}
                  </p>
                  <p>
                    <span className="font-bold text-accent">Cuándo se usa:</span>{" "}
                    {prompt.when_it_runs || "Sin descripción"}
                  </p>
                  <p>
                    <span className="font-bold text-accent">Si lo cambias:</span>{" "}
                    {prompt.if_you_change_it || "Sin descripción"}
                  </p>
                  <p>
                    <span className="font-bold text-accent">Riesgo al tocarlo:</span>{" "}
                    <span className={riskLabelClass(prompt.risk_level)}>
                      {prompt.risk_level || "no definido"}
                    </span>
                  </p>
                </div>

                {prompt.variables.length > 0 ? (
                  <div className="mb-3 flex flex-wrap gap-1">
                    {prompt.variables.map((variable) => (
                      <span
                        key={variable}
                        className="rounded-md border border-accent/30 bg-accent/15 px-2 py-1 font-mono text-[11px] text-accent"
                      >
                        {`{${variable}}`}
                      </span>
                    ))}
                  </div>
                ) : null}

                <textarea
                  value={draft[prompt.id] ?? ""}
                  onChange={(e) => setDraft((prev) => ({ ...prev, [prompt.id]: e.target.value }))}
                  className="min-h-[180px] w-full resize-y rounded-lg border border-border bg-bg p-3 font-mono text-xs leading-relaxed text-text outline-none focus:border-accent"
                  spellCheck={false}
                />

                <div className="mt-2 flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => savePrompt(prompt.id)}
                    className="rounded-md border border-green bg-green/10 px-3 py-1.5 text-xs font-semibold text-green transition hover:bg-green/20"
                  >
                    💾 Guardar
                  </button>
                  <button
                    type="button"
                    onClick={() => resetPrompt(prompt.id)}
                    disabled={!prompt.custom}
                    className="rounded-md border border-border bg-bg px-3 py-1.5 text-xs font-semibold text-text transition hover:border-accent hover:text-accent disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    ↩️ Restaurar Original
                  </button>
                  <span
                    className={`ml-auto text-xs ${msg?.type === "ok" ? "text-green" : "text-red"}`}
                  >
                    {msg?.text || ""}
                  </span>
                </div>
              </article>
            );
          })}
        </div>
      </div>
    </div>
  );
}
