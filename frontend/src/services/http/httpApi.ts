import type { InterviewApi, JoinResult, RoomHandle } from "../api";
import type {
  CanvasOp,
  CanvasSnapshot,
  GuestLink,
  InterviewSession,
  Participant,
  Role,
  ServerMessage,
  User,
} from "../types";
import { recallParticipant, rememberParticipant } from "@/features/room/participantStore";

const DEFAULT_API_URL = "http://localhost:8091/api/v1";
const API_URL = (import.meta.env["VITE_API_URL"] as string | undefined) ?? DEFAULT_API_URL;

// The product has no sign-up/sign-in screen (see openapi.yaml): the mock always
// starts "logged in" as this seeded interviewer. The real backend needs an actual
// session cookie, so we transparently establish one on first owner-scoped call.
const DEMO_OWNER_EMAIL = "jordan@linewarmer.io";

function wsBase(): string {
  const abs = new URL(
    API_URL,
    typeof window !== "undefined" ? window.location.href : "http://localhost",
  );
  abs.protocol = abs.protocol === "https:" ? "wss:" : "ws:";
  return abs.toString().replace(/\/$/, "");
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...(init.headers ?? {}),
    },
  });
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  const body: unknown = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const message =
      body && typeof body === "object" && "message" in body
        ? (body as { message: string }).message
        : res.statusText;
    throw new Error(message);
  }
  return body as T;
}

function participantAuthHeaders(sessionId: string): HeadersInit {
  const token = recallParticipant(sessionId)?.participantToken;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

let ensureSignedInPromise: Promise<void> | null = null;

/** Owner-only calls need an interviewer session cookie; establish one lazily. */
function ensureSignedIn(): Promise<void> {
  ensureSignedInPromise ??= request<User | null>("/auth/me").then((user) => {
    if (user) return;
    return request<User>("/auth/sign-in", {
      method: "POST",
      body: JSON.stringify({ email: DEMO_OWNER_EMAIL }),
    }).then(() => undefined);
  });
  return ensureSignedInPromise;
}

/**
 * Closing a socket while it's still CONNECTING is legal but Chrome logs a scary
 * "WebSocket is closed before the connection is established" console error — most
 * visibly when React's dev-mode double-invoked effects tear down a connection
 * moments after opening it. Defer the close until the handshake finishes instead.
 */
function closeSocket(socket: WebSocket | null): void {
  if (!socket) return;
  if (socket.readyState === WebSocket.CONNECTING) {
    socket.addEventListener("open", () => socket.close(), { once: true });
  } else {
    socket.close();
  }
}

function newClientOperationId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `cop_${Date.now()}_${Math.random().toString(36).slice(2)}`;
}

export class HttpInterviewApi implements InterviewApi {
  /* ---------- auth ---------- */

  getCurrentUser(): Promise<User | null> {
    return request<User | null>("/auth/me");
  }

  signIn(email: string): Promise<User> {
    return request<User>("/auth/sign-in", { method: "POST", body: JSON.stringify({ email }) });
  }

  signOut(): Promise<void> {
    return request<void>("/auth/sign-out", { method: "POST" });
  }

  /* ---------- sessions ---------- */

  async listSessions(): Promise<InterviewSession[]> {
    await ensureSignedIn();
    return request<InterviewSession[]>("/sessions");
  }

  getSession(sessionId: string): Promise<InterviewSession> {
    return request<InterviewSession>(`/sessions/${sessionId}`, {
      headers: participantAuthHeaders(sessionId),
    });
  }

  async createSession(input: {
    title: string;
    prompt: string;
    scheduledAt?: string | null;
  }): Promise<InterviewSession> {
    await ensureSignedIn();
    return request<InterviewSession>("/sessions", { method: "POST", body: JSON.stringify(input) });
  }

  async updateSession(
    sessionId: string,
    patch: Partial<
      Pick<
        InterviewSession,
        "title" | "prompt" | "candidateEditingEnabled" | "cursorsVisible" | "scheduledAt"
      >
    >,
  ): Promise<InterviewSession> {
    await ensureSignedIn();
    return request<InterviewSession>(`/sessions/${sessionId}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    });
  }

  async startSession(sessionId: string): Promise<InterviewSession> {
    await ensureSignedIn();
    return request<InterviewSession>(`/sessions/${sessionId}/start`, { method: "POST" });
  }

  async endSession(sessionId: string): Promise<InterviewSession> {
    await ensureSignedIn();
    return request<InterviewSession>(`/sessions/${sessionId}/end`, { method: "POST" });
  }

  async archiveSession(sessionId: string): Promise<InterviewSession> {
    await ensureSignedIn();
    return request<InterviewSession>(`/sessions/${sessionId}/archive`, { method: "POST" });
  }

  async duplicateSession(sessionId: string): Promise<InterviewSession> {
    await ensureSignedIn();
    return request<InterviewSession>(`/sessions/${sessionId}/duplicate`, { method: "POST" });
  }

  /* ---------- guest links ---------- */

  async listGuestLinks(sessionId: string): Promise<GuestLink[]> {
    await ensureSignedIn();
    return request<GuestLink[]>(`/sessions/${sessionId}/guest-links`);
  }

  async createGuestLink(
    sessionId: string,
    role?: Extract<Role, "candidate" | "observer">,
  ): Promise<GuestLink> {
    await ensureSignedIn();
    return request<GuestLink>(`/sessions/${sessionId}/guest-links`, {
      method: "POST",
      body: JSON.stringify(role ? { role } : {}),
    });
  }

  async revokeGuestLink(sessionId: string, linkId: string): Promise<void> {
    await ensureSignedIn();
    return request<void>(`/sessions/${sessionId}/guest-links/${linkId}`, { method: "DELETE" });
  }

  /* ---------- participants ---------- */

  listParticipants(sessionId: string): Promise<Participant[]> {
    return request<Participant[]>(`/sessions/${sessionId}/participants`, {
      headers: participantAuthHeaders(sessionId),
    });
  }

  async joinWithToken(token: string, displayName: string): Promise<JoinResult> {
    const result = await request<JoinResult & { participantToken: string }>("/join", {
      method: "POST",
      body: JSON.stringify({ token, displayName }),
    });
    rememberParticipant({
      sessionId: result.session.id,
      participantToken: result.participantToken,
    });
    return { session: result.session, participant: result.participant };
  }

  async joinAsOwner(sessionId: string): Promise<JoinResult> {
    await ensureSignedIn();
    return request<JoinResult>(`/sessions/${sessionId}/participants/me`, { method: "POST" });
  }

  async removeParticipant(sessionId: string, participantId: string): Promise<void> {
    await ensureSignedIn();
    return request<void>(`/sessions/${sessionId}/participants/${participantId}`, {
      method: "DELETE",
    });
  }

  /* ---------- canvas ---------- */

  getCanvas(sessionId: string): Promise<CanvasSnapshot> {
    return request<CanvasSnapshot>(`/sessions/${sessionId}/canvas`, {
      headers: participantAuthHeaders(sessionId),
    });
  }

  async clearCanvas(sessionId: string, actorId: string): Promise<void> {
    await ensureSignedIn();
    return request<void>(`/sessions/${sessionId}/canvas/clear`, {
      method: "POST",
      body: JSON.stringify({ actorId }),
    });
  }

  /* ---------- realtime ---------- */

  connect(
    sessionId: string,
    participantId: string,
    onMessage: (msg: ServerMessage) => void,
    onStatus: (status: "connected" | "reconnecting" | "offline") => void,
  ): RoomHandle {
    let ws: WebSocket | null = null;
    let closedByUser = false;
    let dropped = false;
    let forbidden = false;
    let reconnectAttempt = 0;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

    const url = () => {
      const token = recallParticipant(sessionId)?.participantToken;
      const target = new URL(`${wsBase()}/sessions/${sessionId}/room`);
      target.searchParams.set("participantId", participantId);
      if (token) target.searchParams.set("token", token);
      return target.toString();
    };

    const scheduleReconnect = () => {
      if (closedByUser || forbidden) return;
      reconnectAttempt += 1;
      const backoff = Math.min(1000 * reconnectAttempt, 5000);
      reconnectTimer = setTimeout(open, backoff);
    };

    const open = () => {
      onStatus("reconnecting");
      const socket = new WebSocket(url());
      ws = socket;
      socket.onmessage = (event) => {
        const msg = JSON.parse(event.data as string) as ServerMessage;
        if (msg.type === "error" && msg.code === "forbidden") {
          forbidden = true;
          onMessage(msg);
          onStatus("offline");
          return;
        }
        if (msg.type === "room_joined") {
          reconnectAttempt = 0;
          onStatus("connected");
        }
        onMessage(msg);
      };
      socket.onclose = (event) => {
        if (closedByUser || dropped || forbidden) return;
        if (event.code === 4404) {
          forbidden = true;
          onStatus("offline");
          return;
        }
        onStatus("reconnecting");
        scheduleReconnect();
      };
      socket.onerror = () => closeSocket(socket);
    };

    open();

    const send = (payload: unknown) => {
      if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(payload));
    };

    return {
      sendOps: (ops: CanvasOp[]) => {
        send({
          type: "ops",
          ops: ops.map((op) => ({ clientOperationId: newClientOperationId(), op })),
        });
      },
      updatePresence: (patch) => {
        send({ type: "presence", ...patch });
      },
      disconnect: () => {
        closedByUser = true;
        if (reconnectTimer) clearTimeout(reconnectTimer);
        closeSocket(ws);
      },
      simulateNetworkDrop: (ms: number) => {
        dropped = true;
        onStatus("reconnecting");
        closeSocket(ws);
        setTimeout(() => {
          dropped = false;
          open();
        }, ms);
      },
    };
  }
}
