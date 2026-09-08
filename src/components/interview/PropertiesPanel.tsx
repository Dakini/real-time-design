import type { CanvasElement, CanvasOp, InterviewSession } from "@/services/types";
import { useState } from "react";

interface Props {
  session: InterviewSession;
  selected: CanvasElement[];
  canEdit: boolean;
  onCommit: (ops: CanvasOp[]) => void;
}

export function PropertiesPanel({ session, selected, canEdit, onCommit }: Props) {
  const [promptOpen, setPromptOpen] = useState(true);
  const el = selected[0];

  const patch = (next: CanvasElement) => onCommit([{ type: "upsert", element: { ...next, updatedAt: Date.now() } }]);

  return (
    <aside aria-label="Properties" className="flex w-72 shrink-0 flex-col overflow-y-auto border-l border-line bg-panel">
      <div className="border-b border-line p-4">
        <button
          type="button"
          onClick={() => setPromptOpen((v) => !v)}
          className="flex w-full items-center justify-between font-mono text-[10px] tracking-wider text-muted uppercase"
          aria-expanded={promptOpen}
        >
          Prompt
          <span aria-hidden>{promptOpen ? "−" : "+"}</span>
        </button>
        {promptOpen && <p className="mt-2 text-sm leading-relaxed text-ink">{session.prompt}</p>}
      </div>

      <div className="p-4">
        <p className="font-mono text-[10px] tracking-wider text-muted uppercase">Selection</p>
        {!el && <p className="mt-2 text-sm text-muted">Nothing selected.</p>}
        {selected.length > 1 && <p className="mt-2 text-sm text-muted">{selected.length} objects selected.</p>}

        {el && selected.length === 1 && (
          <div className="mt-3 space-y-3">
            <p className="font-mono text-[11px] text-muted">{el.kind}</p>

            {el.kind === "node" && (
              <>
                <Field label="Label">
                  <input
                    value={el.label}
                    disabled={!canEdit}
                    onChange={(e) => patch({ ...el, label: e.target.value })}
                    className="w-full rounded border border-line bg-canvas px-2 py-1 text-sm text-ink"
                  />
                </Field>
                <Field label="Description">
                  <input
                    value={el.description}
                    disabled={!canEdit}
                    onChange={(e) => patch({ ...el, description: e.target.value })}
                    className="w-full rounded border border-line bg-canvas px-2 py-1 text-sm text-ink"
                  />
                </Field>
                <div className="grid grid-cols-2 gap-2">
                  <Field label="Width">
                    <input
                      type="number"
                      value={el.width}
                      disabled={!canEdit}
                      onChange={(e) => patch({ ...el, width: Math.max(80, Number(e.target.value) || 80) })}
                      className="w-full rounded border border-line bg-canvas px-2 py-1 text-sm text-ink"
                    />
                  </Field>
                  <Field label="Height">
                    <input
                      type="number"
                      value={el.height}
                      disabled={!canEdit}
                      onChange={(e) => patch({ ...el, height: Math.max(40, Number(e.target.value) || 40) })}
                      className="w-full rounded border border-line bg-canvas px-2 py-1 text-sm text-ink"
                    />
                  </Field>
                </div>
              </>
            )}

            {(el.kind === "sticky" || el.kind === "text") && (
              <Field label="Text">
                <textarea
                  value={el.text}
                  disabled={!canEdit}
                  rows={4}
                  onChange={(e) => patch({ ...el, text: e.target.value })}
                  className="w-full rounded border border-line bg-canvas px-2 py-1 text-sm text-ink"
                />
              </Field>
            )}

            {el.kind === "connector" && (
              <>
                <Field label="Label">
                  <input
                    value={el.label}
                    disabled={!canEdit}
                    onChange={(e) => patch({ ...el, label: e.target.value })}
                    className="w-full rounded border border-line bg-canvas px-2 py-1 text-sm text-ink"
                  />
                </Field>
                <Field label="Style">
                  <select
                    value={el.style}
                    disabled={!canEdit}
                    onChange={(e) => patch({ ...el, style: e.target.value as typeof el.style })}
                    className="w-full rounded border border-line bg-canvas px-2 py-1 text-sm text-ink"
                  >
                    <option value="straight">Straight</option>
                    <option value="elbow">Elbow</option>
                    <option value="curved">Curved</option>
                  </select>
                </Field>
                <label className="flex items-center gap-2 text-sm text-ink">
                  <input
                    type="checkbox"
                    checked={el.dashed}
                    disabled={!canEdit}
                    onChange={(e) => patch({ ...el, dashed: e.target.checked })}
                  />
                  Dashed
                </label>
                <label className="flex items-center gap-2 text-sm text-ink">
                  <input
                    type="checkbox"
                    checked={el.arrowEnd}
                    disabled={!canEdit}
                    onChange={(e) => patch({ ...el, arrowEnd: e.target.checked })}
                  />
                  Arrow head
                </label>
              </>
            )}

            {canEdit && (
              <button
                type="button"
                onClick={() => onCommit(selected.map((s) => ({ type: "delete", id: s.id }) as CanvasOp))}
                className="mt-2 w-full rounded border border-destructive px-2 py-1.5 text-xs font-medium text-destructive hover:bg-destructive hover:text-destructive-foreground"
              >
                Delete selection
              </button>
            )}
          </div>
        )}
      </div>
    </aside>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block font-mono text-[10px] tracking-wider text-muted uppercase">{label}</span>
      {children}
    </label>
  );
}
