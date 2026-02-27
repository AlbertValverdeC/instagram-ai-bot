interface SlidesPreviewProps {
  slides: string[];
  cacheBust: number;
  onOpen: (slides: string[], index: number) => void;
}

export function SlidesPreview({ slides, cacheBust, onOpen }: SlidesPreviewProps) {
  return (
    <section className="flex flex-col overflow-hidden rounded-xl border border-border-dark bg-secondary-dark">
      {/* Header */}
      <div className="flex items-center justify-between rounded-t-xl border-b border-border-dark bg-surface-dark/50 px-4 py-3">
        <h3 className="flex items-center gap-2 font-display text-base font-bold text-white">
          <span className="material-symbols-outlined text-primary">view_carousel</span>
          Sesión actual · Slides
        </h3>
        <span className="text-xs text-text-subtle">{slides.length} slides</span>
      </div>

      {/* Grid */}
      <div className="flex-1 bg-[#0f151b] p-4">
        {slides.length === 0 ? (
          <p className="text-sm italic text-text-subtle">
            No hay slides en la sesión actual.
          </p>
        ) : (
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            {slides.map((slide, index) => {
              const src = `/slides/${slide}?t=${cacheBust}`;
              return (
                <button
                  key={slide}
                  type="button"
                  onClick={() => onOpen(slides, index)}
                  className="group relative aspect-[4/5] cursor-pointer overflow-hidden rounded-lg border border-border-dark bg-surface-dark shadow-md transition-all hover:ring-2 hover:ring-primary"
                >
                  <img
                    src={src}
                    alt={slide}
                    loading="lazy"
                    className="absolute inset-0 h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-black/20" />
                  <div className="absolute right-2 top-2 rounded border border-white/10 bg-black/60 px-1.5 py-0.5 font-mono text-[10px] text-white backdrop-blur-sm">
                    {String(index + 1).padStart(2, "0")}
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}
