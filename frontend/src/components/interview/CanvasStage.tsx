import { useCallback, useEffect, useRef, useState } from "react";
import type {
  CanvasElement,
  CanvasOp,
  ConnectorElement,
  NodeElement,
  PresenceState,
  StickyElement,
  StrokeElement,
  TextElement,
} from "@/services/types";
import { boxOf, centerOf } from "@/canvas/document";
import { specFor } from "@/canvas/palette";
import { cn } from "@/lib/utils";

export type Tool =
  | "select"
  | "pan"
  | "pen"
  | "highlighter"
  | "eraser"
  | "text"
  | "sticky"
  | "connector";

export interface ViewState {
  scale: number;
  offsetX: number;
  offsetY: number;
}

interface Props {
  elements: CanvasElement[];
  presence: PresenceState[];
  cursorsVisible: boolean;
  selfParticipantId: string;
  canEdit: boolean;
  tool: Tool;
  pendingComponent: string | null;
  onComponentPlaced: () => void;
  selection: string[];
  onSelectionChange: (ids: string[]) => void;
  onCommit: (ops: CanvasOp[]) => void;
  onCursorMove: (point: { x: number; y: number } | null) => void;
  view: ViewState;
  onViewChange: (view: ViewState) => void;
}

let seq = 0;
function newId(prefix: string) {
  seq += 1;
  return `${prefix}_${Date.now().toString(36)}${seq.toString(36)}`;
}

const GRID = 10;
const snap = (n: number) => Math.round(n / GRID) * GRID;

export function CanvasStage(props: Props) {
  const {
    elements,
    presence,
    cursorsVisible,
    selfParticipantId,
    canEdit,
    tool,
    pendingComponent,
    onComponentPlaced,
    selection,
    onSelectionChange,
    onCommit,
    onCursorMove,
    view,
    onViewChange,
  } = props;

  const ref = useRef<HTMLDivElement>(null);
  const [draft, setDraft] = useState<CanvasElement | null>(null);
  const [drag, setDrag] = useState<{ ids: string[]; startX: number; startY: number; originals: CanvasElement[] } | null>(null);
  const [connectFrom, setConnectFrom] = useState<string | null>(null);
  const [panning, setPanning] = useState<{ x: number; y: number; ox: number; oy: number } | null>(null);
  const [previewOffset, setPreviewOffset] = useState<{ dx: number; dy: number } | null>(null);

  const toWorld = useCallback(
    (clientX: number, clientY: number) => {
      const rect = ref.current?.getBoundingClientRect();
      if (!rect) return { x: 0, y: 0 };
      return {
        x: (clientX - rect.left - view.offsetX) / view.scale,
        y: (clientY - rect.top - view.offsetY) / view.scale,
      };
    },
    [view],
  );

  const handleWheel = useCallback(
    (e: React.WheelEvent) => {
      if (!e.ctrlKey && !e.metaKey) {
        onViewChange({ ...view, offsetX: view.offsetX - e.deltaX, offsetY: view.offsetY - e.deltaY });
        return;
      }
      const next = Math.min(2.5, Math.max(0.2, view.scale * (e.deltaY > 0 ? 0.92 : 1.08)));
      onViewChange({ ...view, scale: next });
    },
    [view, onViewChange],
  );

  const createAt = useCallback(
    (world: { x: number; y: number }) => {
      if (!canEdit) return;
      if (pendingComponent) {
        const spec = specFor(pendingComponent);
        if (!spec) return;
        const el: NodeElement = {
          id: newId("el"),
          kind: "node",
          componentType: spec.type,
          label: spec.label,
          description: spec.description,
          x: snap(world.x - spec.width / 2),
          y: snap(world.y - spec.height / 2),
          width: spec.width,
          height: spec.height,
          createdBy: selfParticipantId,
          updatedAt: Date.now(),
        };
        onCommit([{ type: "upsert", element: el }]);
        onSelectionChange([el.id]);
        onComponentPlaced();
        return;
      }
      if (tool === "sticky") {
        const el: StickyElement = {
          id: newId("el"),
          kind: "sticky",
          text: "New note",
          x: snap(world.x),
          y: snap(world.y),
          width: 176,
          height: 96,
          createdBy: selfParticipantId,
          updatedAt: Date.now(),
        };
        onCommit([{ type: "upsert", element: el }]);
        onSelectionChange([el.id]);
      }
      if (tool === "text") {
        const el: TextElement = {
          id: newId("el"),
          kind: "text",
          text: "Label",
          x: snap(world.x),
          y: snap(world.y),
          createdBy: selfParticipantId,
          updatedAt: Date.now(),
        };
        onCommit([{ type: "upsert", element: el }]);
        onSelectionChange([el.id]);
      }
    },
    [canEdit, pendingComponent, tool, onCommit, onSelectionChange, onComponentPlaced, selfParticipantId],
  );

  const handlePointerDown = (e: React.PointerEvent) => {
    const world = toWorld(e.clientX, e.clientY);
    const target = e.target as HTMLElement;
    const elementId = target.closest<HTMLElement>("[data-element-id]")?.dataset["elementId"] ?? null;

    if (tool === "pan" || e.button === 1) {
      setPanning({ x: e.clientX, y: e.clientY, ox: view.offsetX, oy: view.offsetY });
      return;
    }

    if (tool === "pen" || tool === "highlighter") {
      if (!canEdit) return;
      const stroke: StrokeElement = {
        id: newId("el"),
        kind: "stroke",
        points: [world.x, world.y],
        color: tool === "highlighter" ? "amber" : "ink",
        width: tool === "highlighter" ? 14 : 2.5,
        highlighter: tool === "highlighter",
        createdBy: selfParticipantId,
        updatedAt: Date.now(),
      };
      setDraft(stroke);
      return;
    }

    if (tool === "eraser") {
      if (!canEdit || !elementId) return;
      onCommit([{ type: "delete", id: elementId }]);
      return;
    }

    if (tool === "connector") {
      if (!canEdit || !elementId) return;
      if (!connectFrom) {
        setConnectFrom(elementId);
        return;
      }
      if (connectFrom !== elementId) {
        const connector: ConnectorElement = {
          id: newId("el"),
          kind: "connector",
          fromId: connectFrom,
          toId: elementId,
          label: "",
          style: "curved",
          dashed: false,
          arrowEnd: true,
          createdBy: selfParticipantId,
          updatedAt: Date.now(),
        };
        onCommit([{ type: "upsert", element: connector }]);
        onSelectionChange([connector.id]);
      }
      setConnectFrom(null);
      return;
    }

    if (pendingComponent || tool === "sticky" || tool === "text") {
      createAt(world);
      return;
    }

    // select tool
    if (!elementId) {
      onSelectionChange([]);
      setPanning({ x: e.clientX, y: e.clientY, ox: view.offsetX, oy: view.offsetY });
      return;
    }
    const nextSelection = e.shiftKey
      ? selection.includes(elementId)
        ? selection.filter((s) => s !== elementId)
        : [...selection, elementId]
      : selection.includes(elementId)
        ? selection
        : [elementId];
    onSelectionChange(nextSelection);
    if (!canEdit) return;
    setDrag({
      ids: nextSelection,
      startX: world.x,
      startY: world.y,
      originals: elements.filter((el) => nextSelection.includes(el.id)),
    });
  };

  const handlePointerMove = (e: React.PointerEvent) => {
    const world = toWorld(e.clientX, e.clientY);
    onCursorMove(world);

    if (panning) {
      onViewChange({
        ...view,
        offsetX: panning.ox + (e.clientX - panning.x),
        offsetY: panning.oy + (e.clientY - panning.y),
      });
      return;
    }
    if (draft && draft.kind === "stroke") {
      setDraft({ ...draft, points: [...draft.points, world.x, world.y] });
      return;
    }
    if (drag) {
      setPreviewOffset({ dx: world.x - drag.startX, dy: world.y - drag.startY });
    }
  };

  const handlePointerUp = () => {
    if (panning) setPanning(null);
    if (draft && draft.kind === "stroke") {
      if (draft.points.length > 3) onCommit([{ type: "upsert", element: draft }]);
      setDraft(null);
    }
    if (drag && previewOffset) {
      const ops: CanvasOp[] = drag.originals
        .map((el) => {
          const box = boxOf(el);
          if (!box || el.kind === "stroke" || el.kind === "connector") return null;
          return {
            type: "upsert" as const,
            element: {
              ...el,
              x: snap(box.x + previewOffset.dx),
              y: snap(box.y + previewOffset.dy),
              updatedAt: Date.now(),
            } as CanvasElement,
          };
        })
        .filter((op): op is Extract<CanvasOp, { type: "upsert" }> => op !== null);
      if (ops.length) onCommit(ops);
    }
    setDrag(null);
    setPreviewOffset(null);
  };

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const tag = (e.target as HTMLElement | null)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      if ((e.key === "Delete" || e.key === "Backspace") && selection.length && canEdit) {
        e.preventDefault();
        onCommit(selection.map((elementId) => ({ type: "delete" as const, id: elementId })));
        onSelectionChange([]);
      }
      if (e.key === "Escape") {
        onSelectionChange([]);
        setConnectFrom(null);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selection, canEdit, onCommit, onSelectionChange]);

  const offsetFor = (el: CanvasElement) =>
    previewOffset && drag?.ids.includes(el.id) ? previewOffset : { dx: 0, dy: 0 };

  const connectors = elements.filter((el): el is ConnectorElement => el.kind === "connector");
  const strokes = elements.filter((el): el is StrokeElement => el.kind === "stroke");

  return (
    <div
      ref={ref}
      role="application"
      aria-label="Interview canvas"
      className={cn(
        "relative flex-1 dotgrid overflow-hidden touch-none",
        tool === "pan" && "cursor-grab",
        (tool === "pen" || tool === "highlighter") && "cursor-crosshair",
        tool === "eraser" && "cursor-cell",
      )}
      onWheel={handleWheel}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onPointerLeave={() => {
        handlePointerUp();
        onCursorMove(null);
      }}
    >
      <div
        className="absolute left-0 top-0 origin-top-left"
        style={{ transform: `translate(${view.offsetX}px, ${view.offsetY}px) scale(${view.scale})` }}
      >
        <svg className="pointer-events-none absolute left-0 top-0 overflow-visible" width="1" height="1">
          <defs>
            <marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
              <path d="M0 0L6 3L0 6" fill="none" stroke="currentColor" strokeWidth="1.2" />
            </marker>
          </defs>
          {connectors.map((connector) => {
            const from = elements.find((el) => el.id === connector.fromId);
            const to = elements.find((el) => el.id === connector.toId);
            if (!from || !to) return null;
            const a = centerOf(from);
            const b = centerOf(to);
            if (!a || !b) return null;
            const ao = offsetFor(from);
            const bo = offsetFor(to);
            const p1 = { x: a.x + ao.dx, y: a.y + ao.dy };
            const p2 = { x: b.x + bo.dx, y: b.y + bo.dy };
            const midX = (p1.x + p2.x) / 2;
            const d =
              connector.style === "straight"
                ? `M ${p1.x} ${p1.y} L ${p2.x} ${p2.y}`
                : connector.style === "elbow"
                  ? `M ${p1.x} ${p1.y} L ${midX} ${p1.y} L ${midX} ${p2.y} L ${p2.x} ${p2.y}`
                  : `M ${p1.x} ${p1.y} C ${midX} ${p1.y}, ${midX} ${p2.y}, ${p2.x} ${p2.y}`;
            const selected = selection.includes(connector.id);
            return (
              <g key={connector.id} className={selected ? "text-amberdeep" : "text-ink/40"}>
                <path
                  d={d}
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={selected ? 2.2 : 1.5}
                  strokeDasharray={connector.dashed ? "4 4" : undefined}
                  markerEnd={connector.arrowEnd ? "url(#arrow)" : undefined}
                />
                <path
                  d={d}
                  fill="none"
                  stroke="transparent"
                  strokeWidth={14}
                  data-element-id={connector.id}
                  className="pointer-events-auto cursor-pointer"
                />
                {connector.label ? (
                  <text
                    x={midX}
                    y={(p1.y + p2.y) / 2 - 6}
                    textAnchor="middle"
                    className="fill-muted font-mono"
                    fontSize="10"
                  >
                    {connector.label}
                  </text>
                ) : null}
              </g>
            );
          })}

          {[...strokes, ...(draft && draft.kind === "stroke" ? [draft] : [])].map((stroke) => (
            <polyline
              key={stroke.id}
              data-element-id={stroke.id}
              points={pointsToString(stroke.points)}
              fill="none"
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={stroke.width}
              className={cn(
                "pointer-events-auto",
                stroke.highlighter ? "stroke-amber opacity-40" : "stroke-ink",
                selection.includes(stroke.id) && "opacity-100",
              )}
            />
          ))}
        </svg>

        {elements
          .filter((el) => el.kind === "node" || el.kind === "sticky" || el.kind === "text")
          .map((el) => {
            const off = offsetFor(el);
            const selected = selection.includes(el.id);
            const connecting = connectFrom === el.id;
            const box = boxOf(el)!;
            const remote = presence.find(
              (p) => p.participantId !== selfParticipantId && p.selection.includes(el.id),
            );
            return (
              <div
                key={el.id}
                data-element-id={el.id}
                tabIndex={0}
                role="button"
                aria-label={labelOf(el)}
                onFocus={() => onSelectionChange([el.id])}
                className={cn(
                  "absolute rounded-lg outline-none",
                  el.kind === "node" && "bg-panel px-3 py-2.5 shadow-sm ring-1 ring-ink/10",
                  el.kind === "sticky" && "bg-amber/25 p-3 shadow-sm ring-1 ring-amber/40 -rotate-2 rounded-md",
                  el.kind === "text" && "px-1",
                  selected && "ring-2 ring-amberdeep",
                  connecting && "ring-2 ring-remote",
                  remote && "ring-2 ring-remote",
                )}
                style={{
                  left: box.x + off.dx,
                  top: box.y + off.dy,
                  width: el.kind === "text" ? undefined : box.width,
                  height: el.kind === "text" ? undefined : box.height,
                }}
              >
                {el.kind === "node" && (
                  <>
                    <p className="text-[11px] font-semibold">{el.label}</p>
                    <p className="text-[10px] text-muted">{el.description}</p>
                  </>
                )}
                {el.kind === "sticky" && (
                  <p className="text-[11px] leading-snug text-ink/80">{el.text}</p>
                )}
                {el.kind === "text" && <p className="text-[13px] font-medium">{el.text}</p>}
                {remote ? (
                  <span
                    className="absolute -top-5 left-0 rounded px-1.5 py-0.5 text-[9px] font-medium text-panel"
                    style={{ backgroundColor: `var(--${remote.color})` }}
                  >
                    {remote.displayName}
                  </span>
                ) : null}
              </div>
            );
          })}

        {cursorsVisible &&
          presence
            .filter((p) => p.participantId !== selfParticipantId && p.cursor)
            .map((p) => (
              <div
                key={p.participantId}
                className="pointer-events-none absolute"
                style={{ left: p.cursor!.x, top: p.cursor!.y }}
              >
                <svg className="size-4" viewBox="0 0 24 24" style={{ fill: `var(--${p.color})` }}>
                  <path d="M4 3l16 7-7 2-2 7z" />
                </svg>
                <span
                  className="ml-3 inline-block rounded px-1.5 py-0.5 text-[10px] font-medium text-canvas"
                  style={{ backgroundColor: `var(--${p.color})` }}
                >
                  {p.displayName}
                </span>
              </div>
            ))}
      </div>
    </div>
  );
}

function pointsToString(points: number[]): string {
  const out: string[] = [];
  for (let i = 0; i < points.length; i += 2) out.push(`${points[i]},${points[i + 1]}`);
  return out.join(" ");
}

function labelOf(el: CanvasElement): string {
  if (el.kind === "node") return `${el.label} component`;
  if (el.kind === "sticky") return `Sticky note: ${el.text}`;
  if (el.kind === "text") return `Text: ${el.text}`;
  return el.kind;
}
