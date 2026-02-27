import { useEffect } from "react";

interface LightboxProps {
  open: boolean;
  slides: string[];
  index: number;
  cacheBust: number;
  onClose: () => void;
  onPrev: () => void;
  onNext: () => void;
}

export function Lightbox({
  open,
  slides,
  index,
  cacheBust,
  onClose,
  onPrev,
  onNext,
}: LightboxProps) {
  useEffect(() => {
    if (!open) {
      return;
    }

    const onKey = (event: KeyboardEvent) => {
      if (event.key === "ArrowLeft") {
        event.preventDefault();
        onPrev();
      }
      if (event.key === "ArrowRight") {
        event.preventDefault();
        onNext();
      }
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      }
    };

    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose, onNext, onPrev]);

  if (!open || slides.length === 0) {
    return null;
  }

  const src = `/slides/${slides[index]}?t=${cacheBust}`;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/85"
      onClick={onClose}
    >
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          onClose();
        }}
        className="absolute right-5 top-4 text-4xl text-white/70 transition hover:text-white"
      >
        ×
      </button>
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          onPrev();
        }}
        className="absolute left-5 top-1/2 flex h-12 w-12 -translate-y-1/2 items-center justify-center rounded-full border border-white/20 bg-white/10 text-3xl text-white transition hover:bg-white/25"
      >
        ‹
      </button>
      <img
        src={src}
        alt={slides[index]}
        onClick={(e) => e.stopPropagation()}
        className="max-h-[90vh] max-w-[70vw] rounded-lg shadow-2xl"
      />
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          onNext();
        }}
        className="absolute right-5 top-1/2 flex h-12 w-12 -translate-y-1/2 items-center justify-center rounded-full border border-white/20 bg-white/10 text-3xl text-white transition hover:bg-white/25"
      >
        ›
      </button>
      <div className="absolute bottom-6 left-1/2 -translate-x-1/2 text-sm font-semibold text-white/80">
        {index + 1} / {slides.length}
      </div>
    </div>
  );
}
