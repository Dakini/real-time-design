import { createFileRoute, useNavigate, useParams } from "@tanstack/react-router";
import { useState } from "react";
import { api } from "@/services";
import { rememberParticipant } from "@/features/room/participantStore";

export const Route = createFileRoute("/join/$token")({
  head: () => ({
    meta: [
      { title: "Join your interview — Linewarmer" },
      { name: "description", content: "Enter your display name to join the shared system design canvas." },
      { property: "og:title", content: "Join your interview — Linewarmer" },
      { property: "og:description", content: "Enter your display name to join the interview canvas." },
    ],
  }),
  component: Lobby,
});

function Lobby() {
  const { token } = useParams({ from: "/join/$token" });
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const join = async (e: React.FormEvent) => {
    e.preventDefault();
    if (name.trim().length < 2) {
      setError("Please enter the name your interviewer will see.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const { session, participant } = await api.joinWithToken(token, name.trim());
      rememberParticipant({
        sessionId: session.id,
        participantId: participant.id,
        displayName: participant.displayName,
        role: participant.role,
      });
      await navigate({ to: "/room/$sessionId", params: { sessionId: session.id } });
    } catch (err) {
      setError(err instanceof Error ? err.message : "This link can't be used.");
      setBusy(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-canvas px-6">
      <div className="w-full max-w-md rounded-lg border border-line bg-panel p-8">
        <p className="font-mono text-[11px] tracking-[0.16em] text-muted uppercase">Linewarmer</p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight text-ink">Join the interview</h1>
        <p className="mt-2 text-sm text-muted">
          You'll share an infinite canvas with your interviewer. Everything drawn on the canvas is saved
          with the interview record.
        </p>

        <form onSubmit={join} className="mt-6 space-y-4">
          <label className="block">
            <span className="mb-1 block font-mono text-[10px] tracking-wider text-muted uppercase">
              Display name
            </span>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Alex Chen"
              className="w-full rounded border border-line bg-canvas px-3 py-2 text-sm text-ink"
            />
          </label>

          {error && (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={busy}
            className="w-full rounded bg-ink px-4 py-2 text-sm font-medium text-canvas hover:opacity-90 disabled:opacity-50"
          >
            {busy ? "Joining…" : "Join interview"}
          </button>
        </form>

        <p className="mt-5 text-xs text-muted">
          Best on a recent desktop version of Chrome, Edge, Firefox or Safari. Phone editing isn't supported.
        </p>
      </div>
    </main>
  );
}
