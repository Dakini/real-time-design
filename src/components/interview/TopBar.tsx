import { Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import type { ConnectionStatus, InterviewSession, PresenceState, Role } from "@/services/types";
import { cn } from "@/lib/utils";

interface Props {
  session: InterviewSession;
  status: ConnectionStatus;
  presence: PresenceState[];
  role: Role | null;
  onShare?: () => void;
  onEnd?: () => void;
  onSimulateDrop?: () => void;
}

const STATUS_TEXT: Record<ConnectionStatus, string> = {
  connected: "Connected",
  reconnecting: "Reconnecting…",
  offline: "Offline",
};

function useElapsed(startedAt: string | null, endedAt: string | null) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (endedAt) return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [endedAt]);
  if (!startedAt) return "—";
  const end = endedAt ? new Date(endedAt).getTime() : now;
  const secs = Math.max(0, Math.floor((end - new Date(startedAt).getTime()) / 1000));
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

export function TopBar({ session, status, presence, role, onShare, onEnd, onSimulateDrop }: Props) {
  const timer = useElapsed(session.startedAt, session.endedAt);
  const isOwner = role === "owner";

  return (
    <header className="flex h-14 shrink-0 items-center gap-4 border-b border-line bg-panel px-4">
      <Link to="/" className="font-mono text-[11px] tracking-[0.16em] text-muted uppercase hover:text-ink">
        Linewarmer
      </Link>
      <div className="min-w-0">
        <h1 className="truncate text-sm font-semibold text-ink">{session.title}</h1>
        <p className="font-mono text-[10px] tracking-wider text-muted uppercase">
          {session.state} · {timer}
        </p>
      </div>

      <div className="ml-auto flex items-center gap-3">
        <span className="flex items-center gap-1.5 text-xs text-muted" role="status">
          <span
            aria-hidden
            className={cn(
              "inline-block h-2 w-2 rounded-full",
              status === "connected" && "bg-amber pulse-dot",
              status === "reconnecting" && "bg-amberdeep",
              status === "offline" && "bg-destructive",
            )}
          />
          {STATUS_TEXT[status]}
        </span>

        <ul className="flex items-center -space-x-1.5" aria-label="Participants">
          {presence.map((p) => (
            <li
              key={p.participantId}
              title={`${p.displayName} · ${p.role}`}
              className="flex h-7 w-7 items-center justify-center rounded-full border border-panel bg-canvas text-[10px] font-semibold text-ink"
            >
              {p.displayName.slice(0, 2).toUpperCase()}
            </li>
          ))}
        </ul>

        {onSimulateDrop && (
          <button
            type="button"
            onClick={onSimulateDrop}
            className="rounded border border-line px-2 py-1 text-xs text-muted hover:text-ink"
          >
            Simulate drop
          </button>
        )}
        {isOwner && onShare && (
          <button
            type="button"
            onClick={onShare}
            className="rounded bg-ink px-3 py-1.5 text-xs font-medium text-canvas hover:opacity-90"
          >
            Share
          </button>
        )}
        {isOwner && onEnd && session.state === "live" && (
          <button
            type="button"
            onClick={onEnd}
            className="ml-2 rounded border border-destructive px-3 py-1.5 text-xs font-medium text-destructive hover:bg-destructive hover:text-destructive-foreground"
          >
            End interview
          </button>
        )}
      </div>
    </header>
  );
}
