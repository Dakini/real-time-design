import { createFileRoute, Link, useParams } from "@tanstack/react-router";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { api } from "@/services";
import type { GuestLink, Participant, Role } from "@/services/types";
import { useRoom } from "@/features/room/useRoom";
import { recallParticipant, rememberParticipant } from "@/features/room/participantStore";
import { CanvasStage, type Tool, type ViewState } from "@/components/interview/CanvasStage";
import { ToolRail } from "@/components/interview/ToolRail";
import { ComponentLibrary } from "@/components/interview/ComponentLibrary";
import { TopBar } from "@/components/interview/TopBar";
import { PropertiesPanel } from "@/components/interview/PropertiesPanel";
import { fitView } from "@/canvas/document";

export const Route = createFileRoute("/room/$sessionId")({
  head: () => ({
    meta: [
      { title: "Live interview canvas — Linewarmer" },
      {
        name: "description",
        content: "Collaborate on a shared system design canvas in real time.",
      },
      { property: "og:title", content: "Live interview canvas — Linewarmer" },
      {
        property: "og:description",
        content: "Collaborate on a shared system design canvas in real time.",
      },
    ],
  }),
  component: RoomScreen,
});

function RoomScreen() {
  const { sessionId } = useParams({ from: "/room/$sessionId" });
  const [me, setMe] = useState<Participant | null>(null);
  const [joinError, setJoinError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const stored = recallParticipant(sessionId);
    const bootstrap = async () => {
      if (stored) {
        const list = await api.listParticipants(sessionId);
        const found = list.find((p) => p.id === stored.participantId && !p.leftAt);
        if (found) {
          if (!cancelled) setMe(found);
          return;
        }
      }
      try {
        const { participant } = await api.joinAsOwner(sessionId);
        rememberParticipant({
          sessionId,
          participantId: participant.id,
          displayName: participant.displayName,
          role: participant.role,
        });
        if (!cancelled) setMe(participant);
      } catch (err) {
        if (!cancelled)
          setJoinError(err instanceof Error ? err.message : "Could not join this session.");
      }
    };
    void bootstrap();
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  if (joinError) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-canvas px-6">
        <div className="max-w-sm text-center">
          <h1 className="text-lg font-semibold text-ink">This interview isn't available</h1>
          <p className="mt-2 text-sm text-muted">{joinError}</p>
          <Link to="/" className="mt-5 inline-block rounded bg-ink px-4 py-2 text-sm text-canvas">
            Back to interviews
          </Link>
        </div>
      </main>
    );
  }

  if (!me) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-canvas">
        <p className="text-sm text-muted">Opening the canvas…</p>
      </main>
    );
  }

  return <Room sessionId={sessionId} participantId={me.id} role={me.role} />;
}

function Room({
  sessionId,
  participantId,
  role,
}: {
  sessionId: string;
  participantId: string;
  role: Role;
}) {
  const room = useRoom(sessionId, participantId, role);
  const [tool, setTool] = useState<Tool>("select");
  const [libraryOpen, setLibraryOpen] = useState(true);
  const [pending, setPending] = useState<string | null>(null);
  const [selection, setSelection] = useState<string[]>([]);
  const [view, setView] = useState<ViewState>({ scale: 1, offsetX: 0, offsetY: 0 });
  const [links, setLinks] = useState<GuestLink[]>([]);

  const session = room.session;
  const isOwner = role === "owner";

  useEffect(() => {
    if (!isOwner) return;
    void api.listGuestLinks(sessionId).then(setLinks);
  }, [isOwner, sessionId]);

  useEffect(() => {
    room.setSelection(selection);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selection]);

  useEffect(() => {
    if (room.error) toast.error(room.error);
  }, [room.error]);

  const selected = useMemo(
    () => room.elements.filter((el) => selection.includes(el.id)),
    [room.elements, selection],
  );

  const zoomToFit = useCallback(() => {
    const stage = document.getElementById("canvas-stage");
    setView(
      fitView(room.elements, {
        width: stage?.clientWidth ?? 1000,
        height: stage?.clientHeight ?? 700,
      }),
    );
  }, [room.elements]);

  const share = async () => {
    const live =
      links.find((l) => !l.revokedAt) ?? (await api.createGuestLink(sessionId, "candidate"));
    setLinks(await api.listGuestLinks(sessionId));
    const url = `${window.location.origin}/join/${live.token}`;
    try {
      await navigator.clipboard.writeText(url);
      toast.success("Candidate link copied");
    } catch {
      toast.message(url);
    }
  };

  if (!session) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-canvas">
        <p className="text-sm text-muted">Loading interview…</p>
      </main>
    );
  }

  const ended = session.state === "ended" || session.state === "archived";

  return (
    <div className="flex h-screen flex-col bg-canvas">
      <TopBar
        session={session}
        status={room.status}
        presence={room.presence}
        role={role}
        onShare={share}
        onEnd={async () => {
          if (!window.confirm("End this interview? Candidates lose editing immediately.")) return;
          await api.endSession(sessionId);
          toast.success("Interview ended — canvas is read-only for candidates.");
        }}
        onSimulateDrop={room.simulateDrop}
      />

      {ended && (
        <div className="flex items-center justify-between gap-3 border-b border-line bg-panel px-4 py-2">
          <p className="text-xs text-muted">
            This interview has ended. The final canvas is saved for review.
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => {
                const exportPayload = {
                  session,
                  canvas: {
                    sessionId,
                    elements: room.elements,
                    updatedAt: new Date().toISOString(),
                  },
                };
                const blob = new Blob([JSON.stringify(exportPayload, null, 2)], {
                  type: "application/json",
                });
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = `${session.title.replace(/\s+/g, "-").toLowerCase()}.json`;
                a.click();
                URL.revokeObjectURL(url);
              }}
              className="rounded border border-line px-2.5 py-1 text-xs text-ink hover:bg-canvas"
            >
              Export JSON
            </button>
            {isOwner && (
              <button
                type="button"
                onClick={async () => {
                  await api.startSession(sessionId);
                  toast.success("Interview reopened");
                }}
                className="rounded border border-line px-2.5 py-1 text-xs text-ink hover:bg-canvas"
              >
                Reopen
              </button>
            )}
          </div>
        </div>
      )}

      <div className="flex min-h-0 flex-1">
        <ToolRail
          tool={tool}
          onToolChange={setTool}
          libraryOpen={libraryOpen}
          onToggleLibrary={() => setLibraryOpen((v) => !v)}
          disabled={!room.canEdit}
        />
        {libraryOpen && (
          <ComponentLibrary
            pending={pending}
            onPick={setPending}
            onClose={() => setLibraryOpen(false)}
          />
        )}

        <div id="canvas-stage" className="relative min-w-0 flex-1">
          <CanvasStage
            elements={room.elements}
            presence={room.presence}
            cursorsVisible={session.cursorsVisible}
            selfParticipantId={participantId}
            canEdit={room.canEdit}
            tool={tool}
            pendingComponent={pending}
            onComponentPlaced={() => setPending(null)}
            selection={selection}
            onSelectionChange={setSelection}
            onCommit={room.send}
            onCursorMove={room.setCursor}
            view={view}
            onViewChange={setView}
          />

          <div className="pointer-events-none absolute inset-x-0 bottom-0 flex justify-center p-3">
            <div className="pointer-events-auto flex items-center gap-1 rounded-full border border-line bg-panel px-2 py-1 shadow-sm">
              <BarButton
                label="Zoom out"
                onClick={() => setView((v) => ({ ...v, scale: Math.max(0.2, v.scale - 0.1) }))}
              >
                −
              </BarButton>
              <span className="w-12 text-center font-mono text-[11px] text-muted">
                {Math.round(view.scale * 100)}%
              </span>
              <BarButton
                label="Zoom in"
                onClick={() => setView((v) => ({ ...v, scale: Math.min(2, v.scale + 0.1) }))}
              >
                +
              </BarButton>
              <BarButton label="Zoom to fit" onClick={zoomToFit}>
                Fit
              </BarButton>
              <BarButton
                label="Reset view"
                onClick={() => setView({ scale: 1, offsetX: 0, offsetY: 0 })}
              >
                Reset
              </BarButton>
              <BarButton label="Undo" onClick={room.undo} disabled={!room.canUndo || !room.canEdit}>
                Undo
              </BarButton>
              <BarButton label="Redo" onClick={room.redo} disabled={!room.canRedo || !room.canEdit}>
                Redo
              </BarButton>
            </div>
          </div>

          {!room.canEdit && !ended && (
            <p className="absolute top-3 left-1/2 -translate-x-1/2 rounded-full border border-line bg-panel px-3 py-1 text-xs text-muted">
              Editing is locked for you right now
            </p>
          )}
        </div>

        <div className="flex h-full min-h-0 flex-col">
          {isOwner && (
            <div className="space-y-2 border-b border-l border-line bg-panel p-4">
              <p className="font-mono text-[10px] tracking-wider text-muted uppercase">
                Session controls
              </p>
              <label className="flex items-center justify-between gap-2 text-sm text-ink">
                Candidate editing
                <input
                  type="checkbox"
                  checked={session.candidateEditingEnabled}
                  onChange={(e) =>
                    void api.updateSession(sessionId, { candidateEditingEnabled: e.target.checked })
                  }
                />
              </label>
              <label className="flex items-center justify-between gap-2 text-sm text-ink">
                Show cursors
                <input
                  type="checkbox"
                  checked={session.cursorsVisible}
                  onChange={(e) =>
                    void api.updateSession(sessionId, { cursorsVisible: e.target.checked })
                  }
                />
              </label>
              {session.state === "draft" && (
                <button
                  type="button"
                  onClick={() => void api.startSession(sessionId)}
                  className="w-full rounded bg-ink px-2 py-1.5 text-xs font-medium text-canvas"
                >
                  Start interview
                </button>
              )}
              <div className="pt-2">
                <button
                  type="button"
                  onClick={async () => {
                    const live = links.filter((l) => !l.revokedAt);
                    for (const l of live) await api.revokeGuestLink(sessionId, l.id);
                    setLinks(await api.listGuestLinks(sessionId));
                    toast.success("Guest links revoked");
                  }}
                  className="w-full rounded border border-line px-2 py-1.5 text-xs text-muted hover:text-ink"
                >
                  Revoke guest links
                </button>
              </div>
              <div className="mt-3 border-t border-line pt-3">
                <button
                  type="button"
                  onClick={async () => {
                    if (
                      !window.confirm(
                        "Clear the whole canvas? This can be undone by the last snapshot.",
                      )
                    )
                      return;
                    await api.clearCanvas(sessionId, participantId);
                  }}
                  className="w-full rounded border border-destructive px-2 py-1.5 text-xs font-medium text-destructive hover:bg-destructive hover:text-destructive-foreground"
                >
                  Clear canvas
                </button>
              </div>
            </div>
          )}
          <PropertiesPanel
            session={session}
            selected={selected}
            canEdit={room.canEdit}
            onCommit={room.send}
          />
        </div>
      </div>
    </div>
  );
}

function BarButton({
  children,
  label,
  onClick,
  disabled,
}: {
  children: React.ReactNode;
  label: string;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      disabled={disabled}
      className="rounded-full px-2.5 py-1 text-xs text-ink hover:bg-canvas disabled:opacity-40"
    >
      {children}
    </button>
  );
}
