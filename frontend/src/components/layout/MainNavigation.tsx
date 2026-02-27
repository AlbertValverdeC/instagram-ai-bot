export type MainView = "create" | "schedule" | "history";

interface MainNavigationProps {
  activeView: MainView;
  onChange: (view: MainView) => void;
  mobile?: boolean;
}

const ITEMS: Array<{
  key: MainView;
  label: string;
  icon: string;
}> = [
  { key: "create", label: "Crear", icon: "auto_awesome" },
  { key: "schedule", label: "Programar", icon: "event_upcoming" },
  { key: "history", label: "Historial", icon: "history" },
];

export function MainNavigation({ activeView, onChange, mobile = false }: MainNavigationProps) {
  if (mobile) {
    return (
      <nav className="fixed bottom-3 left-1/2 z-40 flex w-[calc(100%-1.5rem)] max-w-sm -translate-x-1/2 items-center gap-1 rounded-2xl border border-border-dark bg-secondary-dark/95 p-2 pb-[calc(0.5rem+env(safe-area-inset-bottom))] shadow-2xl backdrop-blur-md md:hidden">
        {ITEMS.map((item) => {
          const active = item.key === activeView;
          return (
            <button
              key={item.key}
              type="button"
              onClick={() => onChange(item.key)}
              className={`flex min-w-0 flex-1 flex-col items-center justify-center gap-0.5 rounded-xl px-2 py-2 text-[11px] font-semibold transition ${
                active
                  ? "bg-primary text-background-dark"
                  : "bg-surface-dark text-text-subtle hover:text-white"
              }`}
            >
              <span className="material-symbols-outlined text-[17px]">{item.icon}</span>
              <span className="truncate">{item.label}</span>
            </button>
          );
        })}
      </nav>
    );
  }

  return (
    <nav className="hidden md:block">
      <div className="mx-auto flex w-full max-w-[1600px] gap-2 px-6 pb-1 pt-4 lg:px-10">
        {ITEMS.map((item) => {
          const active = item.key === activeView;
          return (
            <button
              key={item.key}
              type="button"
              onClick={() => onChange(item.key)}
              className={`inline-flex items-center gap-2 rounded-lg border px-4 py-2 text-sm font-semibold transition ${
                active
                  ? "border-primary bg-primary/15 text-primary"
                  : "border-border-dark bg-secondary-dark text-text-subtle hover:border-white/20 hover:text-white"
              }`}
            >
              <span className="material-symbols-outlined text-[18px]">{item.icon}</span>
              {item.label}
            </button>
          );
        })}
      </div>
    </nav>
  );
}
