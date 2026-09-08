import type { InterviewApi } from "./api";
import { MockInterviewApi } from "./mock/mockApi";

/**
 * Single services boundary for the app.
 * Today it resolves to the in-memory mock so the product runs with no backend.
 * Swapping in a real implementation only touches this file.
 */
export const api: InterviewApi = new MockInterviewApi();

export const mockApi = api as MockInterviewApi;

export type { InterviewApi, JoinResult, RoomHandle } from "./api";
export * from "./types";
