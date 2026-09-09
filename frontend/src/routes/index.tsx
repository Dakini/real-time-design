import { createFileRoute, Link, useRouter } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { api } from "@/services";
import type { InterviewSession } from "@/services/types";
import { toast } from "sonner";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Interview dashboard — Linewarmer" },
      {
        name: "description",
        content:
          "Create, run and review collaborative system design interviews on a shared infinite canvas.",
      },
      { property: "og:title", content: "Interview dashboard — Linewarmer" },
      {
        property: "og:description",
        content: "Create, run and review collaborative system design interviews.",
      },
    ],
  }),
  component: Dashboard,
});

function Dashboard() {
  const router = useRouter();
  const [sessions, setSessions] = useState<InterviewSession[]>([]);
  const [loading, setLoading] = useState(true);

  const refresh = () =>
    api
      .listSessions()
      .then((s) => {
        setSessions(s);
        setLoading(false);
      })
      .catch((err: unknown) => {
        setLoading(false);
        toast.error(err instanceof Error ? err.message : "Could not load interviews.");
      });

  useEffect(() => {
    void refresh();
  }, []);

  const copyLink = async (session: InterviewSession) => {
    const links = await api.listGuestLinks(session.id);
    const live =
      links.find((l) => !l.revokedAt) ?? (await api.createGuestLink(session.id, "candidate"));
    const url = `${window.location.origin}/join/${live.token}`;
    try {
      await navigator.clipboard.writeText(url);
      toast.success("Candidate link copied");
    } catch {
      toast.message(url);
    }
  };

  return (
    <main className="min-h-screen bg-canvas">
      <div className="mx-auto max-w-5xl px-6 py-12">
        <p className="font-mono text-[11px] tracking-[0.16em] text-muted uppercase">Linewarmer</p>
        <div className="mt-2 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight text-ink">Interviews</h1>
            <p className="mt-1 text-sm text-muted">
              Every session, its canvas and its participants — all saved for review.
            </p>
          </div>
          <Link
            to="/sessions/new"
            className="rounded bg-ink px-4 py-2 text-sm font-medium text-canvas hover:opacity-90"
          >
            New interview
          </Link>
        </div>

        <div className="mt-8 overflow-hidden rounded-lg border border-line bg-panel">
          {loading && <p className="p-6 text-sm text-muted">Loading sessions…</p>}
          {!loading && sessions.length === 0 && (
            <p className="p-6 text-sm text-muted">No interviews yet. Create your first one.</p>
          )}
          <ul className="divide-y divide-line">
            {sessions.map((s) => (
              <li key={s.id} className="flex flex-wrap items-center gap-3 px-5 py-4">
                <div className="min-w-0 flex-1">
                  <Link
                    to="/room/$sessionId"
                    params={{ sessionId: s.id }}
                    className="text-sm font-semibold text-ink hover:underline"
                  >
                    {s.title}
                  </Link>
                  <p className="mt-0.5 truncate text-xs text-muted">{s.prompt}</p>
                  <p className="mt-1 font-mono text-[10px] tracking-wider text-muted uppercase">
                    {s.state} · updated {new Date(s.updatedAt).toLocaleString()}
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <Link
                    to="/room/$sessionId"
                    params={{ sessionId: s.id }}
                    className="rounded border border-line px-2.5 py-1 text-xs text-ink hover:bg-canvas"
                  >
                    {s.state === "ended" || s.state === "archived" ? "Review" : "Open"}
                  </Link>
                  <button
                    type="button"
                    onClick={() => void copyLink(s)}
                    className="rounded border border-line px-2.5 py-1 text-xs text-ink hover:bg-canvas"
                  >
                    Copy link
                  </button>
                  <button
                    type="button"
                    onClick={async () => {
                      const copy = await api.duplicateSession(s.id);
                      await refresh();
                      toast.success(`Duplicated as “${copy.title}”`);
                      void router.invalidate();
                    }}
                    className="rounded border border-line px-2.5 py-1 text-xs text-ink hover:bg-canvas"
                  >
                    Duplicate
                  </button>
                  {s.state !== "archived" && (
                    <button
                      type="button"
                      onClick={async () => {
                        await api.archiveSession(s.id);
                        await refresh();
                      }}
                      className="rounded border border-line px-2.5 py-1 text-xs text-muted hover:text-ink"
                    >
                      Archive
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </main>
  );
}
