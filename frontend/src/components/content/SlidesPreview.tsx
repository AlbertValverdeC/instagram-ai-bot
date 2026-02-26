interface SlidesPreviewProps {
  slides: string[];
  cacheBust: number;
  onOpen: (slides: string[], index: number) => void;
}

export function SlidesPreview({ slides, cacheBust, onOpen }: SlidesPreviewProps) {
  return (
    <section className="rounded-xl border border-border bg-card p-5">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-dim">Preview Slides</h2>
      {slides.length === 0 ? (
        <p className="text-sm italic text-dim">Sin slides. Ejecuta el pipeline para generarlos.</p>
      ) : (
        <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
          {slides.map((slide, index) => {
            const src = `/slides/${slide}?t=${cacheBust}`;
            return (
              <button
                key={slide}
                type="button"
                onClick={() => onOpen(slides, index)}
                className="overflow-hidden rounded-md border border-border transition hover:scale-[1.02] hover:border-accent"
              >
                <img src={src} alt={slide} loading="lazy" className="aspect-[1080/1350] w-full object-cover" />
              </button>
            );
          })}
        </div>
      )}
    </section>
  );
}
