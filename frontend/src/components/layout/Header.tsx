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
    label: "System Idle",
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
  const statusCfg = STATUS_CONFIG[status];

  return (
    <header className="sticky top-0 z-50 flex items-center justify-between border-b border-border-dark bg-secondary-dark/50 px-8 py-4 backdrop-blur-md">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <div className="flex size-8 items-center justify-center rounded-lg bg-primary/20 text-primary">
            <span className="material-symbols-outlined">smart_toy</span>
          </div>
          <h1 className="text-xl font-bold tracking-tight text-white">
            <span className="text-primary">IG</span> AI Bot
            <span className="mx-2 font-normal text-text-subtle">|</span>
            <span className="font-normal text-text-subtle">Panel de Control</span>
          </h1>
        </div>

        <div className="hidden gap-2 md:flex">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-border-dark bg-surface-dark px-3 py-1 text-xs font-medium text-text-subtle">
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
        </div>
      </div>

      <div className="flex items-center gap-6">
        <nav className="hidden items-center gap-6 text-sm font-medium text-text-subtle lg:flex">
          <button
            type="button"
            onClick={onOpenSources}
            className="flex items-center gap-1 transition-colors hover:text-primary"
          >
            <span className="material-symbols-outlined text-[18px]">folder_open</span> Fuentes
          </button>
          <button
            type="button"
            onClick={onOpenPrompts}
            className="flex items-center gap-1 transition-colors hover:text-primary"
          >
            <span className="material-symbols-outlined text-[18px]">terminal</span> Prompts
          </button>
          <button
            type="button"
            onClick={onOpenKeys}
            className="flex items-center gap-1 transition-colors hover:text-primary"
          >
            <span className="material-symbols-outlined text-[18px]">key</span> API Keys
          </button>
          <a
            className="flex items-center gap-1 transition-colors hover:text-primary"
            href="/docs"
            target="_blank"
            rel="noreferrer"
          >
            <span className="material-symbols-outlined text-[18px]">description</span> Docs
          </a>
        </nav>

        <div className="hidden h-6 w-px bg-border-dark lg:block" />

        <div className="flex items-center gap-3">
          {/* Token config popover */}
          <div className="relative">
            <button
              type="button"
              onClick={() => setTokenVisible(!tokenVisible)}
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
              <div className="absolute right-0 top-12 z-50 w-72 rounded-xl border border-border-dark bg-secondary-dark p-4 shadow-2xl">
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
                    className="flex-1 rounded-lg bg-primary py-2 text-sm font-bold text-background-dark transition hover:bg-primary/90"
                  >
                    Guardar
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      onClearToken();
                      setTokenVisible(false);
                    }}
                    className="rounded-lg border border-border-dark bg-surface-dark px-4 py-2 text-sm text-text-subtle transition hover:text-white"
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
