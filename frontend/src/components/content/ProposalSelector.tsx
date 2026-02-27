import type { TextProposal } from "../../types";

interface ProposalSelectorProps {
  proposals: TextProposal[];
  selectedId: string | null;
  loading: boolean;
  creatingDraft: boolean;
  onSelect: (id: string) => void;
  onCreateDraft: () => void;
}

function isSelected(selectedId: string | null, proposalId: string): boolean {
  return !!selectedId && selectedId === proposalId;
}

export function ProposalSelector({
  proposals,
  selectedId,
  loading,
  creatingDraft,
  onSelect,
  onCreateDraft,
}: ProposalSelectorProps) {
  return (
    <section className="flex flex-col overflow-hidden rounded-xl border border-border-dark bg-secondary-dark shadow-lg">
      <div className="flex items-center justify-between border-b border-border-dark bg-surface-dark/50 px-6 py-4">
        <h3 className="text-lg font-bold text-white">Nivel 1 · Propuestas de texto</h3>
        <span className="text-xs text-text-subtle">{proposals.length} propuestas</span>
      </div>

      <div className="space-y-4 p-6">
        {loading ? (
          <p className="text-sm italic text-text-subtle">Generando propuestas...</p>
        ) : proposals.length === 0 ? (
          <p className="text-sm italic text-text-subtle">
            Sin propuestas todavía. Ejecuta Nivel 1 para obtener 3 opciones.
          </p>
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

        <div className="flex items-center justify-end">
          <button
            type="button"
            onClick={onCreateDraft}
            disabled={creatingDraft || proposals.length === 0 || !selectedId}
            className="rounded-lg bg-primary px-5 py-2.5 text-sm font-bold text-background-dark transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {creatingDraft ? "Creando draft..." : "Nivel 2 · Generar draft + slides"}
          </button>
        </div>
      </div>
    </section>
  );
}
