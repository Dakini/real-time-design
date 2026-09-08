import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { api } from "@/services";

export const Route = createFileRoute("/sessions/new")({
  head: () => ({
    meta: [
      { title: "New interview — Linewarmer" },
      { name: "description", content: "Set up a system design interview: title, prompt and schedule." },
      { property: "og:title", content: "New interview — Linewarmer" },
      { property: "og:description", content: "Set up a system design interview session." },
    ],
  }),
  component: NewSession,
});

function NewSession() {
  const navigate = useNavigate();
  const [title, setTitle] = useState("");
  const [prompt, setPrompt] = useState("");
  const [scheduledAt, setScheduledAt] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !prompt.trim()) {
      setError("Give the interview a title and a prompt.");
      return;
    }
    setBusy(true);
    try {
      const session = await api.createSession({
        title: title.trim(),
        prompt: prompt.trim(),
        scheduledAt: scheduledAt ? new Date(scheduledAt).toISOString() : null,
      });
      await navigate({ to: "/room/$sessionId", params: { sessionId: session.id } });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create the interview.");
      setBusy(false);
    }
  };

  return (
    <main className="min-h-screen bg-canvas">
      <div className="mx-auto max-w-2xl px-6 py-12">
        <Link to="/" className="font-mono text-[11px] tracking-[0.16em] text-muted uppercase hover:text-ink">
          ← Interviews
        </Link>
        <h1 className="mt-4 text-3xl font-semibold tracking-tight text-ink">New interview</h1>
        <p className="mt-1 text-sm text-muted">
          You can edit the prompt later; the canvas starts as a draft until you begin.
        </p>

        <form onSubmit={submit} className="mt-8 space-y-5 rounded-lg border border-line bg-panel p-6">
          <label className="block">
            <span className="mb-1 block font-mono text-[10px] tracking-wider text-muted uppercase">Title</span>
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Design a global rate limiter"
              className="w-full rounded border border-line bg-canvas px-3 py-2 text-sm text-ink"
            />
          </label>
          <label className="block">
            <span className="mb-1 block font-mono text-[10px] tracking-wider text-muted uppercase">Prompt</span>
            <textarea
              value={prompt}
              rows={5}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="What should the candidate design? Include scale and constraints."
              className="w-full rounded border border-line bg-canvas px-3 py-2 text-sm text-ink"
            />
          </label>
          <label className="block">
            <span className="mb-1 block font-mono text-[10px] tracking-wider text-muted uppercase">
              Scheduled for (optional)
            </span>
            <input
              type="datetime-local"
              value={scheduledAt}
              onChange={(e) => setScheduledAt(e.target.value)}
              className="w-full rounded border border-line bg-canvas px-3 py-2 text-sm text-ink"
            />
          </label>

          {error && <p className="text-sm text-destructive">{error}</p>}

          <button
            type="submit"
            disabled={busy}
            className="rounded bg-ink px-4 py-2 text-sm font-medium text-canvas hover:opacity-90 disabled:opacity-50"
          >
            {busy ? "Creating…" : "Create interview"}
          </button>
        </form>
      </div>
    </main>
  );
}
