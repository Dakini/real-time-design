import type { InterviewApi, JoinResult, RoomHandle } from "../api";
import type {
  CanvasOp,
  CanvasOperationEnvelope,
  CanvasSnapshot,
  GuestLink,
  InterviewSession,
  Participant,
  PresenceState,
  Role,
  ServerMessage,
  User,
} from "../types";
import { applyOp } from "../../canvas/document";
import { PARTICIPANT_COLORS, id, loadDb, saveDb, secureToken, seedDb, type MockDb } from "./store";

const LATENCY = 60;

function delay<T>(value: T, ms = LATENCY): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(value), ms));
}

interface Subscriber {
  sessionId: string;
  participantId: string;
  onMessage: (msg: ServerMessage) => void;
  dropped: boolean;
  queue: ServerMessage[];
}

export class MockInterviewApi implements InterviewApi {
  private db: MockDb;
  private subscribers = new Set<Subscriber>();
  private presence = new Map<string, Map<string, PresenceState>>();
  private channel: BroadcastChannel | null = null;

  constructor(db?: MockDb) {
    this.db = db ?? loadDb();
    if (typeof BroadcastChannel !== "undefined") {
      this.channel = new BroadcastChannel("linewarmer-mock");
      this.channel.onmessage = (event: MessageEvent) => {
        const data = event.data as { sessionId: string; msg: ServerMessage; ops?: CanvasOperationEnvelope[] };
        if (data.ops) {
          this.db = { ...this.db };
          for (const env of data.ops) this.applyEnvelope(env, false);
        }
        this.fanout(data.sessionId, data.msg, false);
      };
    }
  }

  /** Test helper: reset to a deterministic seed. */
  reset(): void {
    this.db = seedDb();
    this.presence.clear();
  }

  private persist() {
    saveDb(this.db);
  }

  private audit(sessionId: string, kind: string, actorId: string) {
    this.db.audit.push({ id: id("aud"), sessionId, actorId, kind, at: new Date().toISOString() });
  }

  private requireSession(sessionId: string): InterviewSession {
    const session = this.db.sessions.find((s) => s.id === sessionId);
    if (!session) throw new Error("Session not found");
    return session;
  }

  private requireOwner(sessionId: string): InterviewSession {
    const session = this.requireSession(sessionId);
    if (session.ownerUserId !== this.db.currentUserId) throw new Error("Forbidden: owner only");
    return session;
  }

  /* ---------- auth ---------- */

  async getCurrentUser(): Promise<User | null> {
    const user = this.db.users.find((u) => u.id === this.db.currentUserId) ?? null;
    return delay(user);
  }

  async signIn(email: string): Promise<User> {
    let user = this.db.users.find((u) => u.email === email);
    if (!user) {
      user = {
        id: id("user"),
        email,
        displayName: email.split("@")[0] ?? "Interviewer",
        createdAt: new Date().toISOString(),
      };
      this.db.users.push(user);
    }
    this.db.currentUserId = user.id;
    this.persist();
    return delay(user);
  }

  async signOut(): Promise<void> {
    this.db.currentUserId = null;
    this.persist();
    return delay(undefined);
  }

  /* ---------- sessions ---------- */

  async listSessions(): Promise<InterviewSession[]> {
    const list = this.db.sessions
      .filter((s) => s.ownerUserId === this.db.currentUserId && s.state !== "archived")
      .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
    return delay(list);
  }

  async getSession(sessionId: string): Promise<InterviewSession> {
    return delay(this.requireSession(sessionId));
  }

  async createSession(input: { title: string; prompt: string; scheduledAt?: string | null }) {
    if (!this.db.currentUserId) throw new Error("Not authenticated");
    const now = new Date().toISOString();
    const session: InterviewSession = {
      id: id("ses"),
      ownerUserId: this.db.currentUserId,
      title: input.title.trim() || "Untitled interview",
      prompt: input.prompt.trim(),
      state: "draft",
      candidateEditingEnabled: true,
      cursorsVisible: true,
      scheduledAt: input.scheduledAt ?? null,
      startedAt: null,
      endedAt: null,
      createdAt: now,
      updatedAt: now,
    };
    this.db.sessions.push(session);
    this.db.elements[session.id] = [];
    this.db.operations[session.id] = [];
    this.db.cursors[session.id] = 0;
    this.audit(session.id, "session.created", this.db.currentUserId);
    this.persist();
    return delay(session);
  }

  async updateSession(sessionId: string, patch: Partial<InterviewSession>) {
    const session = this.requireOwner(sessionId);
    Object.assign(session, patch, { updatedAt: new Date().toISOString() });
    this.persist();
    this.fanout(sessionId, { type: "permission_changed", session });
    return delay(session);
  }

  async startSession(sessionId: string) {
    const session = this.requireOwner(sessionId);
    session.state = "live";
    session.startedAt = session.startedAt ?? new Date().toISOString();
    session.updatedAt = new Date().toISOString();
    this.audit(sessionId, "session.started", session.ownerUserId);
    this.persist();
    this.fanout(sessionId, { type: "permission_changed", session });
    return delay(session);
  }

  async endSession(sessionId: string) {
    const session = this.requireOwner(sessionId);
    session.state = "ended";
    session.candidateEditingEnabled = false;
    session.endedAt = new Date().toISOString();
    session.updatedAt = session.endedAt;
    this.audit(sessionId, "session.ended", session.ownerUserId);
    this.persist();
    this.fanout(sessionId, { type: "session_ended", session });
    return delay(session);
  }

  async archiveSession(sessionId: string) {
    const session = this.requireOwner(sessionId);
    session.state = "archived";
    session.updatedAt = new Date().toISOString();
    this.audit(sessionId, "session.archived", session.ownerUserId);
    this.persist();
    return delay(session);
  }

  async duplicateSession(sessionId: string) {
    const source = this.requireOwner(sessionId);
    const copy = await this.createSession({ title: `${source.title} (copy)`, prompt: source.prompt });
    this.db.elements[copy.id] = (this.db.elements[sessionId] ?? []).map((el) => ({ ...el }));
    this.persist();
    return copy;
  }

  /* ---------- guest links ---------- */

  async listGuestLinks(sessionId: string): Promise<GuestLink[]> {
    this.requireOwner(sessionId);
    return delay(this.db.links.filter((l) => l.sessionId === sessionId && !l.revokedAt));
  }

  async createGuestLink(sessionId: string, role: Extract<Role, "candidate" | "observer"> = "candidate") {
    const session = this.requireOwner(sessionId);
    for (const link of this.db.links) {
      if (link.sessionId === sessionId && link.roleGranted === role && !link.revokedAt) {
        link.revokedAt = new Date().toISOString();
      }
    }
    const link: GuestLink = {
      id: id("lnk"),
      sessionId,
      token: secureToken(),
      roleGranted: role,
      expiresAt: null,
      maxUses: 10,
      uses: 0,
      revokedAt: null,
      createdAt: new Date().toISOString(),
    };
    this.db.links.push(link);
    this.audit(sessionId, "link.rotated", session.ownerUserId);
    this.persist();
    return delay(link);
  }

  async revokeGuestLink(sessionId: string, linkId: string) {
    const session = this.requireOwner(sessionId);
    const link = this.db.links.find((l) => l.id === linkId && l.sessionId === sessionId);
    if (!link) throw new Error("Link not found");
    link.revokedAt = new Date().toISOString();
    this.audit(sessionId, "link.revoked", session.ownerUserId);
    this.persist();
    return delay(undefined);
  }

  /* ---------- participants ---------- */

  async listParticipants(sessionId: string): Promise<Participant[]> {
    return delay(this.db.participants.filter((p) => p.sessionId === sessionId && !p.leftAt));
  }

  private nextColor(sessionId: string): string {
    const used = this.db.participants.filter((p) => p.sessionId === sessionId).length;
    return PARTICIPANT_COLORS[used % PARTICIPANT_COLORS.length]!;
  }

  async joinWithToken(token: string, displayName: string): Promise<JoinResult> {
    const link = this.db.links.find((l) => l.token === token);
    if (!link) throw new Error("This link is not valid.");
    if (link.revokedAt) throw new Error("This link has been revoked by the interviewer.");
    if (link.expiresAt && new Date(link.expiresAt) < new Date()) throw new Error("This link has expired.");
    const session = this.requireSession(link.sessionId);
    if (session.state === "archived") throw new Error("This interview is no longer available.");
    if (session.state === "ended") throw new Error("This interview has ended.");

    const active = this.db.participants.filter((p) => p.sessionId === session.id && !p.leftAt);
    if (link.maxUses !== null && active.length >= link.maxUses) {
      throw new Error("This interview is full.");
    }
    const name = displayName.trim();
    if (name.length < 2) throw new Error("Please enter your name.");

    link.uses += 1;
    const participant: Participant = {
      id: id("pt"),
      sessionId: session.id,
      userId: null,
      displayName: name.slice(0, 40),
      role: link.roleGranted,
      color: this.nextColor(session.id),
      joinedAt: new Date().toISOString(),
      leftAt: null,
    };
    this.db.participants.push(participant);
    this.audit(session.id, "participant.joined", participant.id);
    this.persist();
    return delay({ session, participant });
  }

  async joinAsOwner(sessionId: string): Promise<JoinResult> {
    const session = this.requireSession(sessionId);
    const userId = this.db.currentUserId;
    if (!userId) throw new Error("Not authenticated");
    const role: Role = session.ownerUserId === userId ? "owner" : "interviewer";
    let participant = this.db.participants.find(
      (p) => p.sessionId === sessionId && p.userId === userId && !p.leftAt,
    );
    if (!participant) {
      const user = this.db.users.find((u) => u.id === userId)!;
      participant = {
        id: id("pt"),
        sessionId,
        userId,
        displayName: user.displayName,
        role,
        color: this.nextColor(sessionId),
        joinedAt: new Date().toISOString(),
        leftAt: null,
      };
      this.db.participants.push(participant);
      this.persist();
    }
    return delay({ session, participant });
  }

  async removeParticipant(sessionId: string, participantId: string) {
    const session = this.requireOwner(sessionId);
    const participant = this.db.participants.find((p) => p.id === participantId);
    if (!participant) throw new Error("Participant not found");
    participant.leftAt = new Date().toISOString();
    this.audit(sessionId, "participant.removed", session.ownerUserId);
    this.presence.get(sessionId)?.delete(participantId);
    this.persist();
    this.broadcastPresence(sessionId);
    return delay(undefined);
  }

  /* ---------- canvas ---------- */

  async getCanvas(sessionId: string): Promise<CanvasSnapshot> {
    this.requireSession(sessionId);
    return delay(this.snapshot(sessionId));
  }

  private snapshot(sessionId: string): CanvasSnapshot {
    return {
      sessionId,
      cursor: this.db.cursors[sessionId] ?? 0,
      elements: (this.db.elements[sessionId] ?? []).map((el) => ({ ...el })),
      updatedAt: new Date().toISOString(),
    };
  }

  async clearCanvas(sessionId: string, actorId: string) {
    this.requireOwner(sessionId);
    this.commit(sessionId, actorId, [{ type: "clear" }]);
    return delay(undefined);
  }

  /* ---------- realtime ---------- */

  private applyEnvelope(env: CanvasOperationEnvelope, local = true) {
    const sessionId = this.sessionOfOperation(env);
    if (!sessionId) return;
    const log = (this.db.operations[sessionId] ??= []);
    // duplicate / out-of-order tolerance
    if (log.some((e) => e.clientOperationId === env.clientOperationId)) return;
    log.push(env);
    this.db.elements[sessionId] = applyOp(this.db.elements[sessionId] ?? [], env.op);
    this.db.cursors[sessionId] = Math.max(this.db.cursors[sessionId] ?? 0, env.cursor);
    if (local) this.persist();
  }

  private opSessions = new Map<string, string>();

  private sessionOfOperation(env: CanvasOperationEnvelope): string | undefined {
    return this.opSessions.get(env.id);
  }

  private commit(sessionId: string, actorId: string, ops: CanvasOp[]): CanvasOperationEnvelope[] {
    const envelopes: CanvasOperationEnvelope[] = ops.map((op, index) => {
      const cursor = (this.db.cursors[sessionId] ?? 0) + index + 1;
      const env: CanvasOperationEnvelope = {
        id: id("op"),
        clientOperationId: id("cop"),
        actorId,
        op,
        serverReceivedAt: Date.now(),
        cursor,
      };
      this.opSessions.set(env.id, sessionId);
      return env;
    });
    for (const env of envelopes) this.applyEnvelope(env);
    this.fanout(sessionId, { type: "document_update", ops: envelopes }, true, envelopes);
    return envelopes;
  }

  private fanout(
    sessionId: string,
    msg: ServerMessage,
    crossTab = true,
    ops?: CanvasOperationEnvelope[],
  ) {
    for (const sub of this.subscribers) {
      if (sub.sessionId !== sessionId) continue;
      if (sub.dropped) {
        sub.queue.push(msg);
        continue;
      }
      sub.onMessage(msg);
    }
    if (crossTab && this.channel) {
      this.channel.postMessage({ sessionId, msg, ops });
    }
  }

  private broadcastPresence(sessionId: string) {
    const list = Array.from(this.presence.get(sessionId)?.values() ?? []);
    this.fanout(sessionId, { type: "presence_update", presence: list });
  }

  connect(
    sessionId: string,
    participantId: string,
    onMessage: (msg: ServerMessage) => void,
    onStatus: (status: "connected" | "reconnecting" | "offline") => void,
  ): RoomHandle {
    const session = this.requireSession(sessionId);
    const participant = this.db.participants.find((p) => p.id === participantId);
    if (!participant || participant.leftAt) {
      onMessage({ type: "error", code: "forbidden", message: "You are not a participant of this session." });
      onStatus("offline");
      return {
        sendOps: () => undefined,
        updatePresence: () => undefined,
        disconnect: () => undefined,
        simulateNetworkDrop: () => undefined,
      };
    }

    const room = this.presence.get(sessionId) ?? new Map<string, PresenceState>();
    room.set(participantId, {
      participantId,
      displayName: participant.displayName,
      role: participant.role,
      color: participant.color,
      cursor: null,
      selection: [],
      online: true,
    });
    this.presence.set(sessionId, room);

    const sub: Subscriber = { sessionId, participantId, onMessage, dropped: false, queue: [] };
    this.subscribers.add(sub);

    setTimeout(() => {
      onStatus("connected");
      onMessage({
        type: "room_joined",
        snapshot: this.snapshot(sessionId),
        presence: Array.from(room.values()),
      });
      this.broadcastPresence(sessionId);
    }, LATENCY);

    const canEdit = () => {
      const current = this.requireSession(sessionId);
      if (current.state === "ended" || current.state === "archived") return false;
      if (participant.role === "observer") return false;
      if (participant.role === "candidate") return current.candidateEditingEnabled;
      return true;
    };

    return {
      sendOps: (ops: CanvasOp[]) => {
        if (sub.dropped) {
          sub.queue.push({ type: "error", code: "offline", message: "Queued while offline" });
          return;
        }
        if (!canEdit()) {
          onMessage({
            type: "error",
            code: "editing_locked",
            message: "Editing is locked for you right now.",
          });
          onMessage({ type: "document_update", ops: [] });
          onMessage({
            type: "room_joined",
            snapshot: this.snapshot(sessionId),
            presence: Array.from(this.presence.get(sessionId)?.values() ?? []),
          });
          return;
        }
        this.commit(sessionId, participantId, ops);
      },
      updatePresence: (patch) => {
        if (sub.dropped) return;
        const current = this.presence.get(sessionId)?.get(participantId);
        if (!current) return;
        Object.assign(current, patch);
        this.broadcastPresence(sessionId);
      },
      disconnect: () => {
        this.subscribers.delete(sub);
        this.presence.get(sessionId)?.delete(participantId);
        this.broadcastPresence(sessionId);
      },
      simulateNetworkDrop: (ms: number) => {
        sub.dropped = true;
        onStatus("reconnecting");
        setTimeout(() => {
          sub.dropped = false;
          onStatus("connected");
          // converge without a page reload
          onMessage({
            type: "room_joined",
            snapshot: this.snapshot(sessionId),
            presence: Array.from(this.presence.get(sessionId)?.values() ?? []),
          });
          sub.queue = [];
        }, ms);
      },
    };
  }

  /** exposed for the review screen / support tooling */
  exportJson(sessionId: string): string {
    return JSON.stringify(
      { session: this.requireSession(sessionId), canvas: this.snapshot(sessionId) },
      null,
      2,
    );
  }
}
