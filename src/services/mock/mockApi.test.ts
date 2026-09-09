import { beforeEach, describe, expect, it } from "vitest";
import { MockInterviewApi } from "./mockApi";
import type { CanvasElement, ServerMessage } from "../types";

const node = (id: string): CanvasElement => ({
  id,
  kind: "node",
  componentType: "cache",
  label: "Cache",
  description: "",
  x: 10,
  y: 10,
  width: 120,
  height: 50,
  createdBy: "pt_owner",
  updatedAt: Date.now(),
});

let api: MockInterviewApi;

beforeEach(() => {
  api = new MockInterviewApi();
});

describe("sessions", () => {
  it("creates a session owned by the current user in draft state", async () => {
    const session = await api.createSession({ title: "Design a feed", prompt: "Scale it" });
    expect(session.state).toBe("draft");
    const all = await api.listSessions();
    expect(all.some((s) => s.id === session.id)).toBe(true);
  });

  it("starts, ends and duplicates a session", async () => {
    const session = await api.createSession({ title: "T", prompt: "P" });
    expect((await api.startSession(session.id)).state).toBe("live");
    expect((await api.endSession(session.id)).state).toBe("ended");
    const copy = await api.duplicateSession(session.id);
    expect(copy.id).not.toBe(session.id);
    expect(copy.state).toBe("draft");
    expect(copy.prompt).toBe("P");
  });
});

describe("guest links", () => {
  it("issues a high entropy token and lets a candidate join", async () => {
    const session = await api.createSession({ title: "T", prompt: "P" });
    await api.startSession(session.id);
    const link = await api.createGuestLink(session.id, "candidate");
    expect(link.token.length).toBeGreaterThanOrEqual(32);

    const joined = await api.joinWithToken(link.token, "Alex");
    expect(joined.participant.role).toBe("candidate");
    expect(joined.session.id).toBe(session.id);
  });

  it("rejects joins on a revoked link", async () => {
    const session = await api.createSession({ title: "T", prompt: "P" });
    await api.startSession(session.id);
    const link = await api.createGuestLink(session.id);
    await api.revokeGuestLink(session.id, link.id);
    await expect(api.joinWithToken(link.token, "Alex")).rejects.toThrow();
  });

  it("rejects an unknown token", async () => {
    await expect(api.joinWithToken("not-a-token", "Alex")).rejects.toThrow();
  });
});

describe("realtime room", () => {
  const messages = (list: ServerMessage[]) => (msg: ServerMessage) => list.push(msg);

  it("sends a snapshot on join and fans out updates to everyone", async () => {
    const session = await api.createSession({ title: "T", prompt: "P" });
    await api.startSession(session.id);
    const owner = await api.joinAsOwner(session.id);
    const link = await api.createGuestLink(session.id);
    const guest = await api.joinWithToken(link.token, "Alex");

    const ownerMsgs: ServerMessage[] = [];
    const guestMsgs: ServerMessage[] = [];
    const ownerRoom = api.connect(session.id, owner.participant.id, messages(ownerMsgs), () => {});
    const guestRoom = api.connect(session.id, guest.participant.id, messages(guestMsgs), () => {});

    await new Promise((r) => setTimeout(r, 120));
    expect(ownerMsgs[0]?.type).toBe("room_joined");
    expect(guestMsgs[0]?.type).toBe("room_joined");

    ownerRoom.sendOps([{ type: "upsert", element: node("el_new") }]);
    const update = guestMsgs.find((m) => m.type === "document_update");
    expect(update).toBeTruthy();

    const snapshot = await api.getCanvas(session.id);
    expect(snapshot.elements.some((e) => e.id === "el_new")).toBe(true);

    ownerRoom.disconnect();
    guestRoom.disconnect();
  });

  it("rejects candidate edits while editing is locked", async () => {
    const session = await api.createSession({ title: "T", prompt: "P" });
    await api.startSession(session.id);
    await api.updateSession(session.id, { candidateEditingEnabled: false });
    const link = await api.createGuestLink(session.id);
    const guest = await api.joinWithToken(link.token, "Alex");

    const msgs: ServerMessage[] = [];
    const room = api.connect(session.id, guest.participant.id, messages(msgs), () => {});
    await new Promise((r) => setTimeout(r, 120));

    room.sendOps([{ type: "upsert", element: node("blocked") }]);
    expect(msgs.some((m) => m.type === "error" && m.code === "editing_locked")).toBe(true);
    const snapshot = await api.getCanvas(session.id);
    expect(snapshot.elements.some((e) => e.id === "blocked")).toBe(false);
    room.disconnect();
  });

  it("converges after a simulated network drop without a reload", async () => {
    const session = await api.createSession({ title: "T", prompt: "P" });
    await api.startSession(session.id);
    const owner = await api.joinAsOwner(session.id);
    const msgs: ServerMessage[] = [];
    const statuses: string[] = [];
    const room = api.connect(session.id, owner.participant.id, messages(msgs), (s) => statuses.push(s));
    await new Promise((r) => setTimeout(r, 120));

    room.simulateNetworkDrop(50);
    expect(statuses).toContain("reconnecting");
    await new Promise((r) => setTimeout(r, 140));
    expect(statuses[statuses.length - 1]).toBe("connected");
    expect(msgs.filter((m) => m.type === "room_joined").length).toBeGreaterThan(1);
    room.disconnect();
  });
});
