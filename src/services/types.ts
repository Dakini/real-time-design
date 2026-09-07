export type Role = "owner" | "interviewer" | "candidate" | "observer";

export type SessionState = "draft" | "live" | "ended" | "archived";

export interface User {
  id: string;
  email: string;
  displayName: string;
  createdAt: string;
}

export interface InterviewSession {
  id: string;
  ownerUserId: string;
  title: string;
  prompt: string;
  state: SessionState;
  candidateEditingEnabled: boolean;
  cursorsVisible: boolean;
  scheduledAt: string | null;
  startedAt: string | null;
  endedAt: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface GuestLink {
  id: string;
  sessionId: string;
  token: string;
  roleGranted: Extract<Role, "candidate" | "observer">;
  expiresAt: string | null;
  maxUses: number | null;
  uses: number;
  revokedAt: string | null;
  createdAt: string;
}

export interface Participant {
  id: string;
  sessionId: string;
  userId: string | null;
  displayName: string;
  role: Role;
  color: string;
  joinedAt: string;
  leftAt: string | null;
}

export interface AuditEvent {
  id: string;
  sessionId: string;
  actorId: string;
  kind: string;
  at: string;
}

/* ---------- canvas ---------- */

export type ElementKind = "node" | "sticky" | "text" | "stroke" | "connector";

export interface BaseElement {
  id: string;
  kind: ElementKind;
  createdBy: string;
  updatedAt: number;
}

export interface NodeElement extends BaseElement {
  kind: "node";
  componentType: string;
  label: string;
  description: string;
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface StickyElement extends BaseElement {
  kind: "sticky";
  text: string;
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface TextElement extends BaseElement {
  kind: "text";
  text: string;
  x: number;
  y: number;
}

export interface StrokeElement extends BaseElement {
  kind: "stroke";
  points: number[];
  color: "ink" | "amber" | "remote" | "warm";
  width: number;
  highlighter: boolean;
}

export interface ConnectorElement extends BaseElement {
  kind: "connector";
  fromId: string;
  toId: string;
  label: string;
  style: "straight" | "elbow" | "curved";
  dashed: boolean;
  arrowEnd: boolean;
}

export type CanvasElement =
  | NodeElement
  | StickyElement
  | TextElement
  | StrokeElement
  | ConnectorElement;

export type CanvasOp =
  | { type: "upsert"; element: CanvasElement }
  | { type: "delete"; id: string }
  | { type: "clear" };

export interface CanvasOperationEnvelope {
  id: string;
  clientOperationId: string;
  actorId: string;
  op: CanvasOp;
  serverReceivedAt: number;
  cursor: number;
}

export interface CanvasSnapshot {
  sessionId: string;
  cursor: number;
  elements: CanvasElement[];
  updatedAt: string;
}

/* ---------- realtime ---------- */

export interface PresenceState {
  participantId: string;
  displayName: string;
  role: Role;
  color: string;
  cursor: { x: number; y: number } | null;
  selection: string[];
  online: boolean;
}

export type ServerMessage =
  | { type: "room_joined"; snapshot: CanvasSnapshot; presence: PresenceState[] }
  | { type: "document_update"; ops: CanvasOperationEnvelope[] }
  | { type: "presence_update"; presence: PresenceState[] }
  | { type: "permission_changed"; session: InterviewSession }
  | { type: "session_ended"; session: InterviewSession }
  | { type: "error"; code: string; message: string };

export type ConnectionStatus = "connected" | "reconnecting" | "offline";
