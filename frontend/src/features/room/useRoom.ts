import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "@/services";
import type {
  CanvasElement,
  CanvasOp,
  ConnectionStatus,
  InterviewSession,
  PresenceState,
  Role,
} from "@/services/types";
import { UndoStack, invert } from "@/canvas/document";
import { categoryOf } from "@/canvas/palette";
import type { RoomHandle } from "@/services/api";

// AI-category components (llm, embedding, vector-db, agent) aren't in the
// backend's componentType allowlist yet, so the server silently drops them.
// Render locally only once we know the op won't be rejected, rather than
// showing something that then has to un-render itself later.
function isAcceptedByServer(op: CanvasOp): boolean {
  if (op.type !== "upsert" || op.element.kind !== "node") return true;
  return categoryOf(op.element.componentType) !== "AI";
}

export interface RoomApi {
  session: InterviewSession | null;
  elements: CanvasElement[];
  presence: PresenceState[];
  status: ConnectionStatus;
  error: string | null;
  ready: boolean;
  canEdit: boolean;
  role: Role | null;
  send: (ops: CanvasOp[]) => void;
  undo: () => void;
  redo: () => void;
  canUndo: boolean;
  canRedo: boolean;
  setCursor: (point: { x: number; y: number } | null) => void;
  setSelection: (ids: string[]) => void;
  simulateDrop: () => void;
  lastSavedAt: number | null;
}

export function useRoom(
  sessionId: string | null,
  participantId: string | null,
  role: Role | null,
): RoomApi {
  const [session, setSession] = useState<InterviewSession | null>(null);
  const [elements, setElements] = useState<CanvasElement[]>([]);
  const [presence, setPresence] = useState<PresenceState[]>([]);
  const [status, setStatus] = useState<ConnectionStatus>("reconnecting");
  const [error, setError] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const [lastSavedAt, setLastSavedAt] = useState<number | null>(null);
  const [, forceRender] = useState(0);

  const handleRef = useRef<RoomHandle | null>(null);
  const elementsRef = useRef<CanvasElement[]>([]);
  const undoRef = useRef(new UndoStack());

  elementsRef.current = elements;

  useEffect(() => {
    if (!sessionId || !participantId) return;
    let cancelled = false;
    void api.getSession(sessionId).then((s) => {
      if (!cancelled) setSession(s);
    });

    const handle = api.connect(
      sessionId,
      participantId,
      (msg) => {
        if (cancelled) return;
        switch (msg.type) {
          case "room_joined":
            setElements(msg.snapshot.elements);
            setPresence(msg.presence);
            setReady(true);
            setLastSavedAt(Date.now());
            break;
          case "document_update":
            if (!msg.ops.length) break;
            setElements((prev) => msg.ops.reduce((acc, env) => applyLocal(acc, env.op), prev));
            setLastSavedAt(Date.now());
            break;
          case "presence_update":
            setPresence(msg.presence);
            break;
          case "permission_changed":
            setSession(msg.session);
            break;
          case "session_ended":
            setSession(msg.session);
            break;
          case "error":
            setError(msg.message);
            setTimeout(() => setError(null), 4000);
            break;
        }
      },
      setStatus,
    );
    handleRef.current = handle;

    return () => {
      cancelled = true;
      handle.disconnect();
      handleRef.current = null;
    };
  }, [sessionId, participantId]);

  const canEdit = useMemo(() => {
    if (!session || !role) return false;
    if (session.state === "ended" || session.state === "archived") return false;
    if (role === "observer") return false;
    if (role === "candidate") return session.candidateEditingEnabled;
    return true;
  }, [session, role]);

  const commit = useCallback((ops: CanvasOp[], recordUndo = true) => {
    if (!ops.length) return;
    const renderableOps = ops.filter(isAcceptedByServer);
    if (recordUndo && renderableOps.length) {
      undoRef.current.push(invert(elementsRef.current, renderableOps));
    }
    setElements((prev) => renderableOps.reduce((acc, op) => applyLocal(acc, op), prev));
    handleRef.current?.sendOps(ops);
    forceRender((n) => n + 1);
  }, []);

  const undo = useCallback(() => {
    const result = undoRef.current.undo(elementsRef.current);
    if (!result) return;
    commit(result.ops, false);
    forceRender((n) => n + 1);
  }, [commit]);

  const redo = useCallback(() => {
    const result = undoRef.current.redo(elementsRef.current);
    if (!result) return;
    commit(result.ops, false);
    forceRender((n) => n + 1);
  }, [commit]);

  return {
    session,
    elements,
    presence,
    status,
    error,
    ready,
    canEdit,
    role,
    send: commit,
    undo,
    redo,
    canUndo: undoRef.current.canUndo,
    canRedo: undoRef.current.canRedo,
    setCursor: (point) => handleRef.current?.updatePresence({ cursor: point }),
    setSelection: (ids) => handleRef.current?.updatePresence({ selection: ids }),
    simulateDrop: () => handleRef.current?.simulateNetworkDrop(4000),
    lastSavedAt,
  };
}

function applyLocal(elements: CanvasElement[], op: CanvasOp): CanvasElement[] {
  if (op.type === "clear") return [];
  if (op.type === "delete") {
    return elements.filter(
      (el) => el.id !== op.id && !(el.kind === "connector" && (el.fromId === op.id || el.toId === op.id)),
    );
  }
  const index = elements.findIndex((el) => el.id === op.element.id);
  if (index === -1) return [...elements, op.element];
  const next = [...elements];
  next[index] = op.element;
  return next;
}
