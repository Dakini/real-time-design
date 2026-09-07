import {
  Eraser,
  Hand,
  Highlighter,
  LayoutGrid,
  MousePointer2,
  MoveRight,
  Pencil,
  StickyNote,
  Type,
} from "lucide-react";
import type { Tool } from "./CanvasStage";
import { cn } from "@/lib/utils";

const TOOLS: { tool: Tool; label: string; Icon: typeof Hand }[] = [
  { tool: "select", label: "Select", Icon: MousePointer2 },
  { tool: "pan", label: "Pan", Icon: Hand },
  { tool: "pen", label: "Pen", Icon: Pencil },
  { tool: "highlighter", label: "Highlighter", Icon: Highlighter },
  { tool: "eraser", label: "Eraser", Icon: Eraser },
  { tool: "text", label: "Text", Icon: Type },
  { tool: "sticky", label: "Sticky note", Icon: StickyNote },
  { tool: "connector", label: "Connector", Icon: MoveRight },
];

interface Props {
  tool: Tool;
  onToolChange: (tool: Tool) => void;
  libraryOpen: boolean;
  onToggleLibrary: () => void;
  disabled: boolean;
}

export function ToolRail({ tool, onToolChange, libraryOpen, onToggleLibrary, disabled }: Props) {
  return (
    <aside
      aria-label="Canvas tools"
      className="flex w-14 shrink-0 flex-col items-center gap-1.5 border-r border-line bg-panel py-3"
    >
      {TOOLS.map(({ tool: value, label, Icon }, index) => (
        <div key={value} className="contents">
          {index === 2 && <div className="my-1 w-7 border-t border-line" />}
          <button
            type="button"
            title={label}
            aria-label={label}
            aria-pressed={tool === value}
            disabled={disabled && value !== "select" && value !== "pan"}
            onClick={() => onToolChange(value)}
            className={cn(
              "grid size-9 place-items-center rounded-lg text-muted transition-colors hover:bg-canvas focus-visible:ring-2 focus-visible:ring-amber focus-visible:outline-none disabled:opacity-40",
              tool === value && "bg-amber/15 text-amberdeep ring-1 ring-amber/40",
            )}
          >
            <Icon className="size-4" strokeWidth={1.6} />
          </button>
        </div>
      ))}
      <div className="my-1 w-7 border-t border-line" />
      <button
        type="button"
        title="Component library"
        aria-label="Component library"
        aria-pressed={libraryOpen}
        disabled={disabled}
        onClick={onToggleLibrary}
        className={cn(
          "grid size-9 place-items-center rounded-lg text-muted transition-colors hover:bg-canvas focus-visible:ring-2 focus-visible:ring-amber focus-visible:outline-none disabled:opacity-40",
          libraryOpen && "bg-amber/15 text-amberdeep ring-1 ring-amber/40",
        )}
      >
        <LayoutGrid className="size-4" strokeWidth={1.6} />
      </button>
    </aside>
  );
}
