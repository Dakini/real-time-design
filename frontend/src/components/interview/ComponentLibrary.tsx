import { COMPONENT_LIBRARY, PALETTE_CATEGORIES } from "@/canvas/palette";
import { cn } from "@/lib/utils";

interface Props {
  pending: string | null;
  onPick: (type: string) => void;
  onClose: () => void;
}

export function ComponentLibrary({ pending, onPick, onClose }: Props) {
  return (
    <aside
      aria-label="Component library"
      className="flex w-60 shrink-0 flex-col overflow-y-auto border-r border-line bg-panel"
    >
      <div className="flex h-11 items-center justify-between border-b border-line px-4">
        <span className="text-[11px] font-semibold tracking-[0.12em] text-muted uppercase">Library</span>
        <button
          type="button"
          onClick={onClose}
          className="rounded px-1 text-xs text-muted hover:bg-canvas"
          aria-label="Close component library"
        >
          Close
        </button>
      </div>
      <div className="space-y-4 p-3">
        {PALETTE_CATEGORIES.map((category) => (
          <div key={category}>
            <p className="mb-1.5 font-mono text-[10px] tracking-wider text-muted uppercase">{category}</p>
            <div className="grid gap-1">
              {COMPONENT_LIBRARY.filter((c) => c.category === category).map((spec) => (
                <button
                  key={spec.type}
                  type="button"
                  onClick={() => onPick(spec.type)}
                  className={cn(
                    "rounded-md px-2.5 py-1.5 text-left ring-1 ring-line transition-colors hover:bg-canvas focus-visible:ring-2 focus-visible:ring-amber focus-visible:outline-none",
                    pending === spec.type && "bg-amber/15 ring-amber/50",
                  )}
                >
                  <span className="block text-[12px] font-medium">{spec.label}</span>
                  <span className="block text-[10px] text-muted">{spec.description}</span>
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
      <p className="mt-auto border-t border-line p-3 text-[11px] text-muted">
        {pending ? "Click the canvas to place it." : "Pick a component, then click the canvas."}
      </p>
    </aside>
  );
}
