import { useEffect, useState } from "react";

import { apiClient } from "../../api/client";
import type { ResearchConfig, ResearchConfigResponse } from "../../types";

interface SourcesModalProps {
  open: boolean;
  onClose: () => void;
}

function removeValue(values: string[], target: string): string[] {
  return values.filter((value) => value !== target);
}

function TagList({ values, onRemove }: { values: string[]; onRemove: (value: string) => void }) {
  return (
    <div className="mb-2 flex flex-wrap gap-1">
      {values.map((value) => (
        <span
          key={value}
          className="inline-flex items-center gap-1 rounded-md border border-border-dark bg-surface-dark px-2 py-1 font-mono text-xs text-slate-100"
        >
          {value}
          <button
            type="button"
            onClick={() => onRemove(value)}
            className="text-sm font-bold text-text-subtle transition hover:text-red"
          >
            ×
          </button>
        </span>
      ))}
    </div>
  );
}

export function SourcesModal({ open, onClose }: SourcesModalProps) {
  const [config, setConfig] = useState<ResearchConfig | null>(null);
  const [isCustom, setIsCustom] = useState(false);
  const [saving, setSaving] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [message, setMessage] = useState<{
    text: string;
    color: "green" | "red" | "orange";
  } | null>(null);
  const [newSubreddit, setNewSubreddit] = useState("");
  const [newFeed, setNewFeed] = useState("");
  const [newKeyword, setNewKeyword] = useState("");

  useEffect(() => {
    if (!open) {
      return;
    }

    (async () => {
      try {
        const data = await apiClient.getResearchConfig();
        setConfig(data.config);
        setIsCustom(data.custom);
      } catch {
        setMessage({ text: "Error cargando config.", color: "red" });
      }
    })();
  }, [open]);

  const addValue = (
    key: keyof Pick<ResearchConfig, "subreddits" | "rss_feeds" | "trends_keywords">,
    value: string,
  ) => {
    const clean = value.trim();
    if (!clean || !config) {
      return;
    }

    if (config[key].includes(clean)) {
      return;
    }

    setConfig({ ...config, [key]: [...config[key], clean] });
  };

  const save = async () => {
    if (!config) {
      return;
    }
    try {
      setSaving(true);
      await apiClient.saveResearchConfig(config);
      setIsCustom(true);
      setMessage({ text: "Guardado correctamente", color: "green" });
    } catch (error) {
      const err = error as Error;
      setMessage({ text: err.message || "Error al guardar", color: "red" });
    } finally {
      setSaving(false);
    }
  };

  const reset = async () => {
    if (!window.confirm("Restaurar todas las fuentes a los valores originales?")) {
      return;
    }

    try {
      setResetting(true);
      await apiClient.resetResearchConfig();
      const data: ResearchConfigResponse = await apiClient.getResearchConfig();
      setConfig(data.config);
      setIsCustom(false);
      setMessage({ text: "Restaurado a originales", color: "green" });
    } catch {
      setMessage({ text: "Error al restaurar", color: "red" });
    } finally {
      setResetting(false);
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
        className="max-h-[90vh] w-[760px] max-w-[95vw] overflow-y-auto rounded-xl border border-border-dark bg-secondary-dark shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-border-dark bg-secondary-dark px-6 py-5">
          <h2 className="font-display text-lg font-bold">
            📡 Fuentes de Investigacion{" "}
            {isCustom ? (
              <span className="ml-1 rounded-full bg-green/20 px-2 py-0.5 text-[10px] font-bold uppercase text-green">
                Personalizado
              </span>
            ) : null}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="text-2xl text-text-subtle transition hover:text-white"
          >
            ×
          </button>
        </div>

        <div className="space-y-5 px-6 py-5">
          {!config ? (
            <p className="text-sm italic text-text-subtle">Cargando...</p>
          ) : (
            <>
              <section>
                <h3 className="mb-1 text-xs font-bold uppercase tracking-wide text-primary">
                  Subreddits
                </h3>
                <p className="mb-2 text-xs text-text-subtle">
                  Subreddits de Reddit de los que se extraen posts trending.
                </p>
                <TagList
                  values={config.subreddits}
                  onRemove={(value) =>
                    setConfig({ ...config, subreddits: removeValue(config.subreddits, value) })
                  }
                />
                <div className="flex gap-2">
                  <input
                    value={newSubreddit}
                    onChange={(e) => setNewSubreddit(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        addValue("subreddits", newSubreddit);
                        setNewSubreddit("");
                      }
                    }}
                    className="flex-1 rounded-md border border-border-dark bg-surface-dark px-3 py-2 font-mono text-xs text-slate-100 outline-none focus:border-primary"
                    placeholder="Nuevo subreddit (ej: LocalLLaMA)"
                  />
                  <button
                    type="button"
                    onClick={() => {
                      addValue("subreddits", newSubreddit);
                      setNewSubreddit("");
                    }}
                    className="rounded-md border border-border-dark bg-surface-dark px-3 py-2 text-sm font-semibold text-slate-100 transition hover:border-primary hover:text-primary"
                  >
                    +
                  </button>
                </div>
              </section>

              <section>
                <h3 className="mb-1 text-xs font-bold uppercase tracking-wide text-primary">
                  RSS Feeds
                </h3>
                <p className="mb-2 text-xs text-text-subtle">
                  URLs de feeds RSS/Atom. Se extraen los 10 artículos más recientes de cada uno.
                </p>
                <TagList
                  values={config.rss_feeds}
                  onRemove={(value) =>
                    setConfig({ ...config, rss_feeds: removeValue(config.rss_feeds, value) })
                  }
                />
                <div className="flex gap-2">
                  <input
                    value={newFeed}
                    onChange={(e) => setNewFeed(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        addValue("rss_feeds", newFeed);
                        setNewFeed("");
                      }
                    }}
                    className="flex-1 rounded-md border border-border-dark bg-surface-dark px-3 py-2 font-mono text-xs text-slate-100 outline-none focus:border-primary"
                    placeholder="URL del feed (ej: https://example.com/feed/)"
                  />
                  <button
                    type="button"
                    onClick={() => {
                      addValue("rss_feeds", newFeed);
                      setNewFeed("");
                    }}
                    className="rounded-md border border-border-dark bg-surface-dark px-3 py-2 text-sm font-semibold text-slate-100 transition hover:border-primary hover:text-primary"
                  >
                    +
                  </button>
                </div>
              </section>

              <section>
                <h3 className="mb-1 text-xs font-bold uppercase tracking-wide text-primary">
                  Google Trends Keywords
                </h3>
                <p className="mb-2 text-xs text-text-subtle">
                  Solo se muestran tendencias que contengan alguna de estas palabras.
                </p>
                <TagList
                  values={config.trends_keywords}
                  onRemove={(value) =>
                    setConfig({
                      ...config,
                      trends_keywords: removeValue(config.trends_keywords, value),
                    })
                  }
                />
                <div className="flex gap-2">
                  <input
                    value={newKeyword}
                    onChange={(e) => setNewKeyword(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        addValue("trends_keywords", newKeyword);
                        setNewKeyword("");
                      }
                    }}
                    className="flex-1 rounded-md border border-border-dark bg-surface-dark px-3 py-2 font-mono text-xs text-slate-100 outline-none focus:border-primary"
                    placeholder="Nueva keyword (ej: blockchain)"
                  />
                  <button
                    type="button"
                    onClick={() => {
                      addValue("trends_keywords", newKeyword);
                      setNewKeyword("");
                    }}
                    className="rounded-md border border-border-dark bg-surface-dark px-3 py-2 text-sm font-semibold text-slate-100 transition hover:border-primary hover:text-primary"
                  >
                    +
                  </button>
                </div>
              </section>

              <section>
                <h3 className="mb-1 text-xs font-bold uppercase tracking-wide text-primary">
                  NewsAPI Dominios
                </h3>
                <p className="mb-2 text-xs text-text-subtle">
                  Dominios separados por coma. Dejar vacío para top-headlines genéricos.
                </p>
                <input
                  value={config.newsapi_domains}
                  onChange={(e) => setConfig({ ...config, newsapi_domains: e.target.value })}
                  className="w-full rounded-md border border-border-dark bg-surface-dark px-3 py-2 font-mono text-xs text-slate-100 outline-none focus:border-primary"
                  placeholder="techcrunch.com,theverge.com,arstechnica.com"
                />
              </section>
            </>
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
          <div className="flex gap-2">
            <button
              type="button"
              disabled={!isCustom || resetting || saving}
              onClick={reset}
              data-loading={resetting ? "true" : undefined}
              className="btn-ghost px-4 py-2"
            >
              {resetting ? "Restaurando..." : "↩️ Restaurar Originales"}
            </button>
            <button
              type="button"
              onClick={save}
              disabled={saving || resetting}
              data-loading={saving ? "true" : undefined}
              className="btn-success px-4 py-2"
            >
              {saving ? "Guardando..." : "💾 Guardar"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
