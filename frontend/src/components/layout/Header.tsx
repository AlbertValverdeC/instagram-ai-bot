import { useState } from "react";
import type { PipelineStatus } from "../../types";

interface HeaderProps {
  status: PipelineStatus;
  tokenConfigured: boolean;
  tokenInput: string;
  onTokenInputChange: (value: string) => void;
  onSaveToken: () => void;
  onClearToken: () => void;
  onOpenSources: () => void;
  onOpenPrompts: () => void;
  onOpenKeys: () => void;
}

const STATUS_CONFIG: Record<
  PipelineStatus,
  { label: string; dotClass: string; badgeClass: string }
> = {
  idle: {
    label: "Listo",
    dotClass: "bg-emerald-500",
    badgeClass: "text-text-subtle",
  },
  running: {
    label: "Ejecutando...",
    dotClass: "bg-orange animate-ping",
    badgeClass: "text-orange",
  },
  done: {
    label: "Completado",
    dotClass: "bg-emerald-500",
    badgeClass: "text-emerald-400",
  },
  error: {
    label: "Error",
    dotClass: "bg-red",
    badgeClass: "text-red",
  },
};

export function Header({
  status,
  tokenConfigured,
  tokenInput,
  onTokenInputChange,
  onSaveToken,
  onClearToken,
  onOpenSources,
  onOpenPrompts,
  onOpenKeys,
}: HeaderProps) {
  const [tokenVisible, setTokenVisible] = useState(false);
  const [toolsVisible, setToolsVisible] = useState(false);
  const statusCfg = STATUS_CONFIG[status];

  return (
    <header className="sticky top-0 z-50 border-b border-border-dark bg-secondary-dark/90 px-3 py-3 backdrop-blur-md sm:px-4">
      <div className="mx-auto flex w-full max-w-[1600px] items-center justify-between gap-3 lg:px-6">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-ig-gradient text-white shadow-glow-ig">
              <span className="material-symbols-outlined text-[18px]">smart_toy</span>
            </div>
            <h1 className="truncate font-display text-base font-bold tracking-tight text-white sm:text-lg">
              IG AI Bot
            </h1>
          </div>
          <p className="mt-0.5 text-[11px] text-text-subtle">Panel móvil primero · flujo simple</p>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <span className="hidden items-center gap-1.5 rounded-full border border-border-dark bg-surface-dark px-2.5 py-1 text-[11px] md:inline-flex">
            <span className="relative flex h-2 w-2">
              <span
                className={`absolute inline-flex h-full w-full rounded-full opacity-75 ${status === "running" ? "animate-ping bg-orange" : ""}`}
              />
              <span
                className={`relative inline-flex h-2 w-2 rounded-full ${statusCfg.dotClass.replace("animate-ping", "")}`}
              />
            </span>
            <span className={statusCfg.badgeClass}>{statusCfg.label}</span>
          </span>

          <div className="relative">
            <button
              type="button"
              onClick={() => {
                setToolsVisible((prev) => !prev);
                setTokenVisible(false);
              }}
              className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-border-dark bg-surface-dark text-text-subtle transition hover:text-white"
              title="Herramientas"
            >
              <span className="material-symbols-outlined text-[20px]">tune</span>
            </button>
            {toolsVisible && (
              <div className="absolute right-0 top-12 z-50 w-48 rounded-xl border border-border-dark bg-secondary-dark p-2 shadow-2xl">
                <button
                  type="button"
                  onClick={() => {
                    onOpenSources();
                    setToolsVisible(false);
                  }}
                  className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm text-text-subtle transition hover:bg-surface-dark hover:text-white"
                >
                  <span className="material-symbols-outlined text-[18px]">folder_open</span>
                  Fuentes
                </button>
                <button
                  type="button"
                  onClick={() => {
                    onOpenPrompts();
                    setToolsVisible(false);
                  }}
                  className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm text-text-subtle transition hover:bg-surface-dark hover:text-white"
                >
                  <span className="material-symbols-outlined text-[18px]">terminal</span>
                  Prompts
                </button>
                <button
                  type="button"
                  onClick={() => {
                    onOpenKeys();
                    setToolsVisible(false);
                  }}
                  className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm text-text-subtle transition hover:bg-surface-dark hover:text-white"
                >
                  <span className="material-symbols-outlined text-[18px]">key</span>
                  API Keys
                </button>
                <a
                  className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm text-text-subtle transition hover:bg-surface-dark hover:text-white"
                  href="/docs"
                  target="_blank"
                  rel="noreferrer"
                  onClick={() => setToolsVisible(false)}
                >
                  <span className="material-symbols-outlined text-[18px]">description</span>
                  Docs
                </a>
              </div>
            )}
          </div>

          <div className="relative">
            <button
              type="button"
              onClick={() => {
                setTokenVisible((prev) => !prev);
                setToolsVisible(false);
              }}
              className={`flex size-10 items-center justify-center rounded-full transition-colors ${
                tokenConfigured
                  ? "bg-emerald-500/15 text-emerald-400 hover:bg-emerald-500/25"
                  : "bg-surface-dark text-text-subtle hover:bg-border-dark"
              }`}
              title={tokenConfigured ? "Token configurado" : "Configurar token"}
            >
              <span className="material-symbols-outlined">
                {tokenConfigured ? "lock" : "lock_open"}
              </span>
            </button>

            {tokenVisible && (
              <div className="absolute right-0 top-12 z-50 w-[min(86vw,18rem)] rounded-xl border border-border-dark bg-secondary-dark p-4 shadow-2xl">
                <label className="mb-2 block text-xs font-semibold uppercase tracking-wider text-text-subtle">
                  API Token
                </label>
                <input
                  type="password"
                  value={tokenInput}
                  onChange={(e) => onTokenInputChange(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      onSaveToken();
                      setTokenVisible(false);
                    }
                  }}
                  placeholder="Pega tu token aquí"
                  className="mb-3 w-full rounded-lg border border-border-dark bg-surface-dark px-3 py-2 text-sm text-white outline-none placeholder:text-text-subtle/50 focus:border-primary focus:ring-1 focus:ring-primary"
                />
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      onSaveToken();
                      setTokenVisible(false);
                    }}
                    className="btn-primary flex-1 py-2"
                  >
                    Guardar
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      onClearToken();
                      setTokenVisible(false);
                    }}
                    className="btn-ghost px-4 py-2"
                  >
                    Limpiar
                  </button>
                </div>
                <p
                  className={`mt-2 text-center text-xs ${tokenConfigured ? "text-emerald-400" : "text-text-subtle"}`}
                >
                  {tokenConfigured ? "Token configurado" : "No configurado"}
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
