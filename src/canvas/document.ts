import type { CanvasElement, CanvasOp } from "../services/types";

/** Deterministic, order-independent-ish application of a single operation. */
export function applyOp(elements: CanvasElement[], op: CanvasOp): CanvasElement[] {
  switch (op.type) {
    case "clear":
      return [];
    case "delete":
      return elements.filter((el) => el.id !== op.id && !(el.kind === "connector" && (el.fromId === op.id || el.toId === op.id)));
    case "upsert": {
      const index = elements.findIndex((el) => el.id === op.element.id);
      if (index === -1) return [...elements, op.element];
      const existing = elements[index]!;
      // last-write-wins per element, ties resolved by element id for determinism
      const incomingWins =
        op.element.updatedAt > existing.updatedAt ||
        (op.element.updatedAt === existing.updatedAt && op.element.id >= existing.id);
      if (!incomingWins) return elements;
      const next = [...elements];
      next[index] = op.element;
      return next;
    }
    default:
      return elements;
  }
}

export function applyOps(elements: CanvasElement[], ops: CanvasOp[]): CanvasElement[] {
  return ops.reduce(applyOp, elements);
}

export function findElement(elements: CanvasElement[], id: string): CanvasElement | undefined {
  return elements.find((el) => el.id === id);
}

export interface Box {
  x: number;
  y: number;
  width: number;
  height: number;
}

export function boxOf(el: CanvasElement): Box | null {
  if (el.kind === "node" || el.kind === "sticky") {
    return { x: el.x, y: el.y, width: el.width, height: el.height };
  }
  if (el.kind === "text") return { x: el.x, y: el.y, width: 120, height: 24 };
  if (el.kind === "stroke") {
    const xs = el.points.filter((_, i) => i % 2 === 0);
    const ys = el.points.filter((_, i) => i % 2 === 1);
    if (!xs.length) return null;
    const minX = Math.min(...xs);
    const minY = Math.min(...ys);
    return { x: minX, y: minY, width: Math.max(...xs) - minX, height: Math.max(...ys) - minY };
  }
  return null;
}

export function centerOf(el: CanvasElement): { x: number; y: number } | null {
  const box = boxOf(el);
  if (!box) return null;
  return { x: box.x + box.width / 2, y: box.y + box.height / 2 };
}

export function fitView(
  elements: CanvasElement[],
  viewport: { width: number; height: number },
): { scale: number; offsetX: number; offsetY: number } {
  const boxes = elements.map(boxOf).filter((b): b is Box => b !== null);
  if (!boxes.length) return { scale: 1, offsetX: 0, offsetY: 0 };
  const minX = Math.min(...boxes.map((b) => b.x));
  const minY = Math.min(...boxes.map((b) => b.y));
  const maxX = Math.max(...boxes.map((b) => b.x + b.width));
  const maxY = Math.max(...boxes.map((b) => b.y + b.height));
  const pad = 80;
  const scale = Math.min(
    2,
    Math.max(0.2, Math.min(viewport.width / (maxX - minX + pad * 2), viewport.height / (maxY - minY + pad * 2))),
  );
  return {
    scale,
    offsetX: viewport.width / 2 - ((minX + maxX) / 2) * scale,
    offsetY: viewport.height / 2 - ((minY + maxY) / 2) * scale,
  };
}

/** Per-participant undo stack: a list of inverse operation batches. */
export class UndoStack {
  private undoStack: CanvasOp[][] = [];
  private redoStack: CanvasOp[][] = [];

  push(inverse: CanvasOp[]) {
    if (!inverse.length) return;
    this.undoStack.push(inverse);
    this.redoStack = [];
  }

  get canUndo() {
    return this.undoStack.length > 0;
  }

  get canRedo() {
    return this.redoStack.length > 0;
  }

  undo(current: CanvasElement[]): { ops: CanvasOp[] } | null {
    const batch = this.undoStack.pop();
    if (!batch) return null;
    this.redoStack.push(invert(current, batch));
    return { ops: batch };
  }

  redo(current: CanvasElement[]): { ops: CanvasOp[] } | null {
    const batch = this.redoStack.pop();
    if (!batch) return null;
    this.undoStack.push(invert(current, batch));
    return { ops: batch };
  }
}

/** Build the inverse of a batch given the state before it is applied. */
export function invert(before: CanvasElement[], ops: CanvasOp[]): CanvasOp[] {
  const inverse: CanvasOp[] = [];
  for (const op of ops) {
    if (op.type === "upsert") {
      const existing = findElement(before, op.element.id);
      inverse.push(
        existing
          ? { type: "upsert", element: { ...existing, updatedAt: Date.now() + 1 } }
          : { type: "delete", id: op.element.id },
      );
    } else if (op.type === "delete") {
      const existing = findElement(before, op.id);
      if (existing) inverse.push({ type: "upsert", element: { ...existing, updatedAt: Date.now() + 1 } });
    } else if (op.type === "clear") {
      for (const el of before) {
        inverse.push({ type: "upsert", element: { ...el, updatedAt: Date.now() + 1 } });
      }
    }
  }
  return inverse.reverse();
}
