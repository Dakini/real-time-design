import { describe, expect, it } from "vitest";
import { applyOp, applyOps, boxOf, fitView, invert, UndoStack } from "./document";
import type { CanvasElement, NodeElement } from "../services/types";

const node = (id: string, updatedAt = 1000): NodeElement => ({
  id,
  kind: "node",
  componentType: "server",
  label: id,
  description: "",
  x: 0,
  y: 0,
  width: 100,
  height: 50,
  createdBy: "pt_1",
  updatedAt,
});

describe("applyOp", () => {
  it("inserts unknown elements", () => {
    expect(applyOp([], { type: "upsert", element: node("a") })).toHaveLength(1);
  });

  it("keeps the newest write and ignores stale ones", () => {
    const start = [node("a", 2000)];
    const stale = applyOp(start, { type: "upsert", element: { ...node("a", 1000), label: "old" } });
    expect((stale[0] as { label: string }).label).toBe("a");
    const fresh = applyOp(start, { type: "upsert", element: { ...node("a", 3000), label: "new" } });
    expect((fresh[0] as { label: string }).label).toBe("new");
  });

  it("deletes an element and its connectors", () => {
    const elements: CanvasElement[] = [
      node("a"),
      node("b"),
      {
        id: "c1",
        kind: "connector",
        fromId: "a",
        toId: "b",
        label: "",
        style: "curved",
        dashed: false,
        arrowEnd: true,
        createdBy: "pt_1",
        updatedAt: 1,
      },
    ];
    expect(applyOp(elements, { type: "delete", id: "a" }).map((e) => e.id)).toEqual(["b"]);
  });

  it("is order independent for edits to different elements", () => {
    const base = [node("a"), node("b")];
    const opA = { type: "upsert" as const, element: { ...node("a", 5000), x: 40 } };
    const opB = { type: "upsert" as const, element: { ...node("b", 5000), x: 90 } };
    const one = applyOps(base, [opA, opB]);
    const two = applyOps(base, [opB, opA]);
    expect(new Map(one.map((e) => [e.id, e]))).toEqual(new Map(two.map((e) => [e.id, e])));
  });

  it("tolerates duplicate application", () => {
    const op = { type: "upsert" as const, element: node("a") };
    expect(applyOps([], [op, op])).toHaveLength(1);
  });
});

describe("undo and redo", () => {
  it("restores prior state per participant", () => {
    const stack = new UndoStack();
    let elements: CanvasElement[] = [];
    const ops = [{ type: "upsert" as const, element: node("a") }];
    stack.push(invert(elements, ops));
    elements = applyOps(elements, ops);
    expect(elements).toHaveLength(1);

    const undone = stack.undo(elements)!;
    elements = applyOps(elements, undone.ops);
    expect(elements).toHaveLength(0);

    const redone = stack.redo(elements)!;
    elements = applyOps(elements, redone.ops);
    expect(elements).toHaveLength(1);
  });
});

describe("geometry", () => {
  it("measures strokes", () => {
    const box = boxOf({
      id: "s",
      kind: "stroke",
      points: [0, 0, 10, 20],
      color: "ink",
      width: 2,
      highlighter: false,
      createdBy: "pt_1",
      updatedAt: 1,
    })!;
    expect(box).toEqual({ x: 0, y: 0, width: 10, height: 20 });
  });

  it("fits an empty canvas to the identity view", () => {
    expect(fitView([], { width: 800, height: 600 })).toEqual({ scale: 1, offsetX: 0, offsetY: 0 });
  });

  it("clamps the fit scale", () => {
    const view = fitView([node("a")], { width: 1200, height: 800 });
    expect(view.scale).toBeLessThanOrEqual(2);
    expect(view.scale).toBeGreaterThanOrEqual(0.2);
  });
});
