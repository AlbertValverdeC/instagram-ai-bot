import type { TextProposal } from "../../types";

interface ProposalSelectorProps {
  proposals: TextProposal[];
  selectedId: string | null;
  loading: boolean;
  canGenerate: boolean;
  onGenerate: () => void;
  onSelect: (id: string) => void;
}

function isSelected(selectedId: string | null, proposalId: string): boolean {
  return !!selectedId && selectedId === proposalId;
}

export function ProposalSelector({
  proposals,
  selectedId,
  loading,
  canGenerate,
  onGenerate,
  onSelect,
}: ProposalSelectorProps) {
  const selectedProposal = proposals.find((proposal) => String(proposal.id || "") === selectedId);

  return (
    <section className="flex flex-col overflow-hidden rounded-xl border border-border-dark bg-secondary-dark shadow-lg">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border-dark bg-surface-dark/50 px-6 py-4">
        <div>
          <h3 className="font-display text-lg font-bold text-white">Propuestas (Paso 1 y 2)</h3>
          <p className="mt-1 text-xs text-text-subtle">
            Paso 1: genera propuestas. Paso 2: elige una tarjeta para continuar.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-text-subtle">{proposals.length} propuestas</span>
          <button
            type="button"
            onClick={onGenerate}
            disabled={!canGenerate}
            className="btn-primary px-4 py-2 text-xs"
          >
            {loading ? "Generando..." : "Generar nuevas"}
          </button>
        </div>
      </div>

      <div className="space-y-4 p-6">
        {loading ? (
          <p className="text-sm italic text-text-subtle">Generando propuestas...</p>
        ) : proposals.length === 0 ? (
          <div className="rounded-lg border border-dashed border-border-dark bg-surface-dark/40 p-5 text-center">
            <p className="text-sm font-semibold text-white">Todavía no hay propuestas</p>
            <p className="mt-1 text-xs text-text-subtle">
              Pulsa <span className="font-semibold text-primary">Generar nuevas</span> para crear
              opciones de texto.
            </p>
            <button
              type="button"
              onClick={onGenerate}
              disabled={!canGenerate}
              className="mt-3 rounded-lg bg-primary px-4 py-2 text-xs font-bold text-background-dark transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Generar propuestas ahora
            </button>
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-3">
            {proposals.map((proposal) => {
              const pid = String(proposal.id || "");
              const selected = isSelected(selectedId, pid);
              return (
                <button
                  key={pid}
                  type="button"
                  onClick={() => onSelect(pid)}
                  className={`text-left rounded-lg border p-4 transition ${
                    selected
                      ? "border-primary bg-primary/10 ring-1 ring-primary"
                      : "border-border-dark bg-surface-dark hover:border-white/30"
                  }`}
                >
                  <p className="text-xs uppercase tracking-wide text-text-subtle">
                    {proposal.angle || "Enfoque"}
                  </p>
                  <p className="mt-2 text-sm font-semibold text-white">{proposal.hook || "-"}</p>
                  <p className="mt-3 text-xs leading-relaxed text-slate-300">
                    {proposal.caption_preview || "-"}
                  </p>
                  <p className="mt-3 text-xs text-primary">{proposal.cta || "-"}</p>
                </button>
              );
            })}
          </div>
        )}

        {selectedProposal && (
          <p className="text-xs text-text-subtle">
            Seleccionada:{" "}
            <span className="font-semibold text-primary">
              {selectedProposal.hook || selectedProposal.id}
            </span>
          </p>
        )}
      </div>
    </section>
  );
}
