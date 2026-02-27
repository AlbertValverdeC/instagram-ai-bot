interface LevelFlowCompactProps {
  disabled: boolean;
  generatingProposals: boolean;
  creatingDraft: boolean;
  liveRunning: boolean;
  proposalsCount: number;
  hasSelectedProposal: boolean;
  hasDraftReady: boolean;
  draftsPendingPublish: number;
  onGenerateProposals: () => void;
  onCreateDraft: () => void;
  onRunLive: () => void;
}

type FlowState = "idle" | "ready" | "running" | "done";

function stateClasses(state: FlowState): string {
  if (state === "running") return "border-primary/60 bg-primary/10";
  if (state === "done") return "border-green/60 bg-green/10";
  if (state === "ready") return "border-orange/60 bg-orange/10";
  return "border-border-dark bg-surface-dark/50";
}

function dotClasses(state: FlowState): string {
  if (state === "running") return "bg-primary animate-pulse";
  if (state === "done") return "bg-green";
  if (state === "ready") return "bg-orange";
  return "bg-border-dark";
}

export function LevelFlowCompact({
  disabled,
  generatingProposals,
  creatingDraft,
  liveRunning,
  proposalsCount,
  hasSelectedProposal,
  hasDraftReady,
  draftsPendingPublish,
  onGenerateProposals,
  onCreateDraft,
  onRunLive,
}: LevelFlowCompactProps) {
  const level1State: FlowState = generatingProposals
    ? "running"
    : proposalsCount > 0
      ? "done"
      : "idle";

  const level2State: FlowState = hasSelectedProposal
    ? "done"
    : proposalsCount > 0
      ? "ready"
      : "idle";
  const level3State: FlowState = creatingDraft
    ? "running"
    : hasDraftReady
      ? "done"
      : hasSelectedProposal
        ? "ready"
        : "idle";
  const level4State: FlowState = liveRunning
    ? "running"
    : draftsPendingPublish > 0
      ? "ready"
      : "idle";

  return (
    <section className="rounded-xl border border-border-dark bg-secondary-dark p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="font-display text-sm font-semibold text-white">Flujo por pasos</p>
          <p className="text-xs text-text-subtle">
            Paso 1 generar propuestas · paso 2 seleccionar · paso 3 crear draft · paso 4 live
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={onGenerateProposals}
            disabled={disabled}
            className="btn-primary px-3.5 py-2 text-xs"
          >
            {generatingProposals ? "Generando..." : "Generar propuestas"}
          </button>
          <button
            type="button"
            onClick={onCreateDraft}
            disabled={disabled || !hasSelectedProposal || proposalsCount === 0}
            className="btn-secondary px-3.5 py-2 text-xs"
          >
            {creatingDraft ? "Creando..." : "Crear draft + slides"}
          </button>
          <button
            type="button"
            onClick={onRunLive}
            disabled={disabled}
            className="btn-danger px-3.5 py-2 text-xs"
          >
            E2E Live
          </button>
        </div>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2.5 lg:grid-cols-4">
        <div className={`rounded-lg border px-3 py-2 ${stateClasses(level1State)}`}>
          <div className="flex items-center justify-between text-[10px] uppercase tracking-wide text-text-subtle">
            <span>Paso 1</span>
            <span className={`inline-block size-2 rounded-full ${dotClasses(level1State)}`} />
          </div>
          <p className="mt-1 text-xs font-semibold text-white">Propuestas</p>
          <p className="mt-0.5 text-[11px] text-text-subtle">{proposalsCount} disponibles</p>
        </div>

        <div className={`rounded-lg border px-3 py-2 ${stateClasses(level2State)}`}>
          <div className="flex items-center justify-between text-[10px] uppercase tracking-wide text-text-subtle">
            <span>Paso 2</span>
            <span className={`inline-block size-2 rounded-full ${dotClasses(level2State)}`} />
          </div>
          <p className="mt-1 text-xs font-semibold text-white">Seleccionar propuesta</p>
          <p className="mt-0.5 text-[11px] text-text-subtle">
            {hasSelectedProposal ? "propuesta elegida" : "elige una tarjeta"}
          </p>
        </div>

        <div className={`rounded-lg border px-3 py-2 ${stateClasses(level3State)}`}>
          <div className="flex items-center justify-between text-[10px] uppercase tracking-wide text-text-subtle">
            <span>Paso 3</span>
            <span className={`inline-block size-2 rounded-full ${dotClasses(level3State)}`} />
          </div>
          <p className="mt-1 text-xs font-semibold text-white">Draft + slides</p>
          <p className="mt-0.5 text-[11px] text-text-subtle">
            {hasDraftReady ? "draft listo" : "pendiente de crear"}
          </p>
        </div>

        <div className={`rounded-lg border px-3 py-2 ${stateClasses(level4State)}`}>
          <div className="flex items-center justify-between text-[10px] uppercase tracking-wide text-text-subtle">
            <span>Paso 4</span>
            <span className={`inline-block size-2 rounded-full ${dotClasses(level4State)}`} />
          </div>
          <p className="mt-1 text-xs font-semibold text-white">Publicar</p>
          <p className="mt-0.5 text-[11px] text-text-subtle">
            {draftsPendingPublish > 0
              ? `${draftsPendingPublish} draft pendientes`
              : liveRunning
                ? "live ejecutando"
                : "sin pendientes"}
          </p>
        </div>
      </div>
    </section>
  );
}
