const KEY = "linewarmer.participant.v1";

export interface StoredParticipant {
  sessionId: string;
  participantId: string;
  displayName: string;
  role: string;
}

function readAll(): Record<string, StoredParticipant> {
  if (typeof window === "undefined") return {};
  try {
    return JSON.parse(window.sessionStorage.getItem(KEY) ?? "{}") as Record<string, StoredParticipant>;
  } catch {
    return {};
  }
}

export function rememberParticipant(entry: StoredParticipant): void {
  if (typeof window === "undefined") return;
  const all = readAll();
  all[entry.sessionId] = entry;
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
