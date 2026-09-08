import type {
  CanvasOp,
  CanvasSnapshot,
  GuestLink,
  InterviewSession,
  Participant,
  PresenceState,
  Role,
  ServerMessage,
  User,
} from "./types";

export interface JoinResult {
  session: InterviewSession;
  participant: Participant;
}

export interface RoomHandle {
  sendOps: (ops: CanvasOp[]) => void;
  updatePresence: (patch: Partial<Pick<PresenceState, "cursor" | "selection">>) => void;
  disconnect: () => void;
  simulateNetworkDrop: (ms: number) => void;
}

/**
 * The single backend boundary for the whole app.
 * Every network-ish call goes through this interface, so the UI never talks to
 * a transport directly and a real backend can be swapped in behind it.
 */
export interface InterviewApi {
  /* auth */
  getCurrentUser(): Promise<User | null>;
  signIn(email: string): Promise<User>;
  signOut(): Promise<void>;

  /* sessions */
  listSessions(): Promise<InterviewSession[]>;
  getSession(id: string): Promise<InterviewSession>;
  createSession(input: { title: string; prompt: string; scheduledAt?: string | null }): Promise<InterviewSession>;
  updateSession(id: string, patch: Partial<Pick<InterviewSession,
    "title" | "prompt" | "candidateEditingEnabled" | "cursorsVisible" | "scheduledAt">>): Promise<InterviewSession>;
  startSession(id: string): Promise<InterviewSession>;
  endSession(id: string): Promise<InterviewSession>;
  archiveSession(id: string): Promise<InterviewSession>;
  duplicateSession(id: string): Promise<InterviewSession>;

  /* guest links */
  listGuestLinks(sessionId: string): Promise<GuestLink[]>;
  createGuestLink(sessionId: string, role?: Extract<Role, "candidate" | "observer">): Promise<GuestLink>;
  revokeGuestLink(sessionId: string, linkId: string): Promise<void>;

  /* participants */
  listParticipants(sessionId: string): Promise<Participant[]>;
  joinWithToken(token: string, displayName: string): Promise<JoinResult>;
  joinAsOwner(sessionId: string): Promise<JoinResult>;
  removeParticipant(sessionId: string, participantId: string): Promise<void>;

  /* canvas */
  getCanvas(sessionId: string): Promise<CanvasSnapshot>;
  clearCanvas(sessionId: string, actorId: string): Promise<void>;

  /* realtime */
  connect(
    sessionId: string,
    participantId: string,
    onMessage: (msg: ServerMessage) => void,
    onStatus: (status: "connected" | "reconnecting" | "offline") => void,
  ): RoomHandle;
}
