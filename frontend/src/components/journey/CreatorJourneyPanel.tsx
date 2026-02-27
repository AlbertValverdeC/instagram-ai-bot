import type { TextProposal } from "../../types";

interface CreatorJourneyPanelProps {
  busy: boolean;
  topic: string;
  proposals: TextProposal[];
  selectedProposalId: string | null;
  generatingProposals: boolean;
  creatingDraft: boolean;
  publishingDraft: boolean;
  draftCount: number;
  onTopicChange: (value: string) => void;
  onFindTopics: () => void;
  onSelectProposal: (id: string) => void;
  onCreateDraft: () => void;
  onPublishLatestDraft: () => void;
}

function proposalId(proposal: TextProposal): string {
  return String(proposal.id || "");
}

function stepStateClass(active: boolean): string {
  return active
    ? "border-primary/50 bg-primary/15 text-primary"
    : "border-border-dark bg-surface-dark text-text-subtle";
}

export function CreatorJourneyPanel({
  busy,
  topic,
  proposals,
  selectedProposalId,
  generatingProposals,
  creatingDraft,
  publishingDraft,
  draftCount,
  onTopicChange,
  onFindTopics,
  onSelectProposal,
  onCreateDraft,
  onPublishLatestDraft,
}: CreatorJourneyPanelProps) {
  const selected =
    proposals.find((proposal) => proposalId(proposal) === selectedProposalId) || null;
  const hasManualTopic = topic.trim().length > 0;
  const modeLabel = hasManualTopic
    ? `Temática manual: "${topic.trim()}"`
    : "Temática automática (si está vacío)";
  const hasProposals = proposals.length > 0;
  const hasDrafts = draftCount > 0;
  const steps = [
    { id: "1", label: "Tema", active: hasProposals || generatingProposals },
    { id: "2", label: "Seleccionar", active: Boolean(selected) },
    { id: "3", label: "Borrador", active: hasDrafts || creatingDraft },
    { id: "4", label: "Publicar", active: publishingDraft },
  ];

  return (
    <section className="overflow-hidden rounded-xl border border-border-dark bg-secondary-dark">
      <div className="border-b border-border-dark bg-surface-dark/35 p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-display text-sm font-bold text-white">Crear carrusel</h2>
          <p className="text-[11px] text-text-subtle">Flujo guiado y rápido</p>
        </div>
        <div className="mt-3 grid grid-cols-4 gap-1.5">
          {steps.map((step) => (
            <div
              key={step.id}
              className={`rounded-md border px-2 py-1.5 text-center text-[10px] font-semibold ${stepStateClass(
                step.active,
              )}`}
            >
              <span className="block text-[9px] opacity-80">Paso {step.id}</span>
              <span className="block truncate">{step.label}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="space-y-4 p-4">
        <div className="group relative w-full min-w-0 flex-1">
          <span className="absolute inset-y-0 left-0 flex items-center pl-3 text-text-subtle transition-colors group-focus-within:text-primary">
            <span className="material-symbols-outlined text-[18px]">search</span>
          </span>
          <input
            value={topic}
            onChange={(e) => onTopicChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                onFindTopics();
              }
            }}
            placeholder="Paso 1: escribe una temática (opcional, vacío = automática)"
            className="w-full rounded-lg border border-border-dark bg-surface-dark py-2.5 pl-10 pr-3 text-sm text-white placeholder-text-subtle/50 transition-all focus:border-primary focus:ring-1 focus:ring-primary"
          />
        </div>

        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <button
            type="button"
            onClick={onFindTopics}
            disabled={busy}
            data-loading={generatingProposals ? "true" : undefined}
            className="btn-primary w-full px-4 py-2.5 text-xs sm:w-auto"
          >
            <span className="material-symbols-outlined text-[16px]">travel_explore</span>
            {generatingProposals ? "Buscando..." : "Paso 1 · Encontrar temáticas"}
          </button>
          <div className="rounded-lg border border-border-dark bg-surface-dark/40 px-3 py-2 sm:flex-1">
            <p className="text-[11px] text-text-subtle">
              Si escribes tema, se usa ese. Si queda vacío, la IA lo decide.
            </p>
            <p className="mt-1 text-[11px] font-semibold text-primary">{modeLabel}</p>
          </div>
        </div>

        <div className="rounded-lg border border-border-dark bg-surface-dark/40 p-3">
          <div className="mb-2 flex items-center justify-between">
            <p className="text-xs font-semibold text-white">Paso 2 · Elige idea</p>
            <span className="text-[11px] text-text-subtle">{proposals.length} opciones</span>
          </div>

          {generatingProposals ? (
            <p className="text-xs text-text-subtle">Generando propuestas...</p>
          ) : proposals.length === 0 ? (
            <p className="text-xs text-text-subtle">No hay propuestas todavía. Ejecuta el paso 1.</p>
          ) : (
            <div className="flex gap-2 overflow-x-auto pb-1 md:grid md:grid-cols-3 md:overflow-visible md:pb-0">
              {proposals.map((proposal) => {
                const pid = proposalId(proposal);
                const isSelected = selectedProposalId === pid;
                return (
                  <button
                    key={pid}
                    type="button"
                    onClick={() => onSelectProposal(pid)}
                    className={`min-w-[82%] rounded-lg border px-3 py-2 text-left transition md:min-w-0 ${
                      isSelected
                        ? "border-primary bg-primary/10 ring-1 ring-primary"
                        : "border-border-dark bg-surface-dark hover:border-white/30"
                    }`}
                  >
                    <div className="mb-1 flex items-center justify-between gap-2">
                      <p className="text-[10px] font-semibold uppercase tracking-wide text-text-subtle">
                        Propuesta
                      </p>
                      {isSelected && (
                        <span className="inline-flex items-center rounded-full border border-primary/40 bg-primary/20 px-1.5 py-0.5 text-[9px] font-semibold text-primary">
                          Seleccionada
                        </span>
                      )}
                    </div>
                    <p className="line-clamp-2 text-xs font-semibold text-white">
                      {proposal.hook || "Propuesta"}
                    </p>
                    <p className="mt-1 line-clamp-2 text-[11px] text-text-subtle">
                      {proposal.caption_preview || proposal.angle || "Sin descripción"}
                    </p>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        <div className="rounded-lg border border-border-dark bg-surface-dark/40 p-3">
          <div className="mb-2 flex items-center justify-between">
            <p className="text-xs font-semibold text-white">Paso 3 y 4 · Ejecutar</p>
            <span className="text-[11px] text-text-subtle">Borradores: {draftCount}</span>
          </div>
          <p className="mb-3 text-[11px] text-text-subtle">
            {selected
              ? "Idea elegida. Puedes crear borrador ahora y publicarlo cuando quieras."
              : "Selecciona una propuesta para continuar."}
          </p>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <button
              type="button"
              onClick={onCreateDraft}
              disabled={busy || !selected}
              data-loading={creatingDraft ? "true" : undefined}
              className="btn-secondary w-full px-4 py-2 sm:w-auto"
            >
              <span className="material-symbols-outlined text-[16px]">draw</span>
              {creatingDraft ? "Creando..." : "Paso 3 · Crear borrador"}
            </button>
            <button
              type="button"
              onClick={onPublishLatestDraft}
              disabled={busy || draftCount === 0}
              data-loading={publishingDraft ? "true" : undefined}
              className="btn-success w-full px-4 py-2 sm:w-auto"
            >
              <span className="material-symbols-outlined text-[16px]">publish</span>
              {publishingDraft ? "Publicando..." : "Paso 4 · Publicar último"}
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
