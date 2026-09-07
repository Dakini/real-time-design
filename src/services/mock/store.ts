import type {
  AuditEvent,
  CanvasElement,
  CanvasOperationEnvelope,
  GuestLink,
  InterviewSession,
  Participant,
  User,
} from "../types";

export interface MockDb {
  users: User[];
  currentUserId: string | null;
  sessions: InterviewSession[];
  links: GuestLink[];
  participants: Participant[];
  elements: Record<string, CanvasElement[]>;
  operations: Record<string, CanvasOperationEnvelope[]>;
  cursors: Record<string, number>;
  audit: AuditEvent[];
}

const STORAGE_KEY = "linewarmer.mockdb.v1";

export const PARTICIPANT_COLORS = ["amberdeep", "warm", "remote", "live"] as const;

let counter = 0;
export function id(prefix: string): string {
  counter += 1;
  const rand = Math.random().toString(36).slice(2, 8);
  return `${prefix}_${Date.now().toString(36)}${counter.toString(36)}${rand}`;
}

/** 128+ bits of entropy, hex encoded. */
export function secureToken(): string {
  const bytes = new Uint8Array(16);
  if (typeof globalThis.crypto?.getRandomValues === "function") {
    globalThis.crypto.getRandomValues(bytes);
  } else {
    for (let i = 0; i < bytes.length; i += 1) bytes[i] = Math.floor(Math.random() * 256);
  }
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

export function seedDb(): MockDb {
  const now = new Date();
  const owner: User = {
    id: "user_owner",
    email: "jordan@linewarmer.io",
    displayName: "Jordan Reyes",
    createdAt: now.toISOString(),
  };

  const iso = (offsetMinutes: number) =>
    new Date(now.getTime() + offsetMinutes * 60_000).toISOString();

  const sessions: InterviewSession[] = [
    {
      id: "ses_ratelimiter",
      ownerUserId: owner.id,
      title: "Design a global rate limiter",
      prompt:
        "Design a distributed rate limiter that enforces per-key quotas at 100k req/s. Cover storage, failure modes, and consistency trade-offs.",
      state: "live",
      candidateEditingEnabled: true,
      cursorsVisible: true,
      scheduledAt: iso(-30),
      startedAt: iso(-28),
      endedAt: null,
      createdAt: iso(-1440),
      updatedAt: iso(-2),
    },
    {
      id: "ses_chatscale",
      ownerUserId: owner.id,
      title: "Chat at 10M concurrent users",
      prompt: "Design a realtime chat backend for 10M concurrent connections with delivery guarantees.",
      state: "ended",
      candidateEditingEnabled: false,
      cursorsVisible: true,
      scheduledAt: iso(-2880),
      startedAt: iso(-2880),
      endedAt: iso(-2820),
      createdAt: iso(-4320),
      updatedAt: iso(-2820),
    },
    {
      id: "ses_cdn",
      ownerUserId: owner.id,
      title: "CDN and edge cache strategy",
      prompt: "Design an edge caching layer for a media-heavy product across three regions.",
      state: "draft",
      candidateEditingEnabled: true,
      cursorsVisible: true,
      scheduledAt: iso(2880),
      startedAt: null,
      endedAt: null,
      createdAt: iso(-120),
      updatedAt: iso(-120),
    },
  ];

  const links: GuestLink[] = [
    {
      id: "lnk_seed",
      sessionId: "ses_ratelimiter",
      token: "demo-candidate-token",
      roleGranted: "candidate",
      expiresAt: null,
      maxUses: 10,
      uses: 1,
      revokedAt: null,
      createdAt: iso(-40),
    },
  ];

  const participants: Participant[] = [
    {
      id: "pt_owner",
      sessionId: "ses_ratelimiter",
      userId: owner.id,
      displayName: owner.displayName,
      role: "owner",
      color: "amberdeep",
      joinedAt: iso(-28),
      leftAt: null,
    },
  ];

  const elements: CanvasElement[] = [
    {
      id: "el_client",
      kind: "node",
      componentType: "browser-client",
      label: "Web Client",
      description: "mobile / browser",
      x: 120,
      y: 220,
      width: 160,
      height: 60,
      createdBy: "pt_owner",
      updatedAt: Date.now(),
    },
    {
      id: "el_gateway",
      kind: "node",
      componentType: "api-gateway",
      label: "API Gateway",
      description: "authn · throttling",
      x: 380,
      y: 170,
      width: 176,
      height: 60,
      createdBy: "pt_owner",
      updatedAt: Date.now(),
    },
    {
      id: "el_cache",
      kind: "node",
      componentType: "cache",
      label: "Redis Cache",
      description: "token bucket",
      x: 660,
      y: 220,
      width: 160,
      height: 60,
      createdBy: "pt_owner",
      updatedAt: Date.now(),
    },
    {
      id: "el_db",
      kind: "node",
      componentType: "relational-db",
      label: "Postgres",
      description: "quotas · rules",
      x: 400,
      y: 400,
      width: 176,
      height: 60,
      createdBy: "pt_owner",
      updatedAt: Date.now(),
    },
    {
      id: "el_goal",
      kind: "sticky",
      text: "Handle 100k req/s with per-key counters, no single point of failure.",
      x: 100,
      y: 60,
      width: 176,
      height: 96,
      createdBy: "pt_owner",
      updatedAt: Date.now(),
    },
    {
      id: "el_c1",
      kind: "connector",
      fromId: "el_client",
      toId: "el_gateway",
      label: "HTTPS",
      style: "curved",
      dashed: false,
      arrowEnd: true,
      createdBy: "pt_owner",
      updatedAt: Date.now(),
    },
    {
      id: "el_c2",
      kind: "connector",
      fromId: "el_gateway",
      toId: "el_cache",
      label: "read",
      style: "curved",
      dashed: false,
      arrowEnd: true,
      createdBy: "pt_owner",
      updatedAt: Date.now(),
    },
    {
      id: "el_c3",
      kind: "connector",
      fromId: "el_gateway",
      toId: "el_db",
      label: "persist",
      style: "curved",
      dashed: true,
      arrowEnd: true,
      createdBy: "pt_owner",
      updatedAt: Date.now(),
    },
  ];

  const endedElements: CanvasElement[] = [
    {
      id: "el_ws",
      kind: "node",
      componentType: "server",
      label: "WebSocket Fleet",
      description: "sticky sessions",
      x: 220,
      y: 180,
      width: 176,
      height: 60,
      createdBy: "pt_owner",
      updatedAt: Date.now(),
    },
    {
      id: "el_fanout",
      kind: "node",
      componentType: "pubsub",
      label: "Fan-out broker",
      description: "per-room topics",
      x: 520,
      y: 260,
      width: 176,
      height: 60,
      createdBy: "pt_owner",
      updatedAt: Date.now(),
    },
    {
      id: "el_ws_c",
      kind: "connector",
      fromId: "el_ws",
      toId: "el_fanout",
      label: "events",
      style: "curved",
      dashed: false,
      arrowEnd: true,
      createdBy: "pt_owner",
      updatedAt: Date.now(),
    },
  ];

  return {
    users: [owner],
    currentUserId: owner.id,
    sessions,
    links,
    participants,
    elements: {
      ses_ratelimiter: elements,
      ses_chatscale: endedElements,
      ses_cdn: [],
    },
    operations: { ses_ratelimiter: [], ses_chatscale: [], ses_cdn: [] },
    cursors: { ses_ratelimiter: 0, ses_chatscale: 0, ses_cdn: 0 },
    audit: [],
  };
}

export function loadDb(): MockDb {
  if (typeof window === "undefined") return seedDb();
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return seedDb();
    return JSON.parse(raw) as MockDb;
  } catch {
    return seedDb();
  }
}

export function saveDb(db: MockDb): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(db));
  } catch {
    /* storage full or unavailable — mock data stays in memory */
  }
}
