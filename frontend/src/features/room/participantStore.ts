const KEY = "linewarmer.participant.v1";

export interface StoredParticipant {
  sessionId: string;
  participantId: string;
  displayName: string;
  role: string;
  /** Bearer credential for guests, issued by `POST /join`. Absent for owners, who use the session cookie. */
  participantToken?: string;
}

function readAll(): Record<string, StoredParticipant> {
  if (typeof window === "undefined") return {};
  try {
    return JSON.parse(window.sessionStorage.getItem(KEY) ?? "{}") as Record<
      string,
      StoredParticipant
    >;
  } catch {
    return {};
  }
}

/** Merges with any existing entry for the session, so callers can update fields independently. */
export function rememberParticipant(
  entry: Partial<StoredParticipant> & Pick<StoredParticipant, "sessionId">,
): void {
  if (typeof window === "undefined") return;
  const all = readAll();
  all[entry.sessionId] = { ...all[entry.sessionId], ...entry } as StoredParticipant;
  window.sessionStorage.setItem(KEY, JSON.stringify(all));
}

export function recallParticipant(sessionId: string): StoredParticipant | null {
  return readAll()[sessionId] ?? null;
}

export function forgetParticipant(sessionId: string): void {
  if (typeof window === "undefined") return;
  const all = readAll();
  delete all[sessionId];
  window.sessionStorage.setItem(KEY, JSON.stringify(all));
}
