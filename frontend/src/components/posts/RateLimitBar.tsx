import type { RateLimitInfo } from "../../types";

interface RateLimitBarProps {
  rateLimit: RateLimitInfo | null;
}

export function RateLimitBar({ rateLimit }: RateLimitBarProps) {
  if (!rateLimit) return null;

  const { count, limit, next_slot_in_minutes } = rateLimit;
  const pct = Math.min(100, Math.round((count / limit) * 100));

  let barColor: string;
  if (pct <= 40) {
    barColor = "bg-green";
  } else if (pct <= 72) {
    barColor = "bg-orange";
  } else {
    barColor = "bg-red";
  }

  let slotLabel: string | null = null;
  if (count >= limit && next_slot_in_minutes != null) {
    const h = Math.floor(next_slot_in_minutes / 60);
    const m = next_slot_in_minutes % 60;
    slotLabel = h > 0 ? `en ${h}h ${m}m` : `en ${m}m`;
  } else if (next_slot_in_minutes != null && count > 0) {
    const h = Math.floor(next_slot_in_minutes / 60);
    const m = next_slot_in_minutes % 60;
    slotLabel = h > 0 ? `en ${h}h ${m}m` : `en ${m}m`;
  }

  return (
    <div className="rounded-xl border border-border-dark bg-secondary-dark p-4">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-sm text-text-subtle">
          Publicaciones 24h:{" "}
          <span className="font-mono font-bold text-white">
            {count} / {limit}
          </span>
        </span>
        {slotLabel && (
          <span className="text-sm text-text-subtle">
            Próximo slot: <span className="font-mono font-bold text-white">{slotLabel}</span>
          </span>
        )}
      </div>
      <div className="h-2.5 w-full rounded-full bg-border-dark">
        <div
          className={`h-2.5 rounded-full transition-all ${barColor}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
