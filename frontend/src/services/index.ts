import type { InterviewApi } from "./api";
import { HttpInterviewApi } from "./http/httpApi";

/**
 * Single services boundary for the app.
 * Resolves to the FastAPI backend (see ../../backend); swapping implementations
 * only touches this file.
 */
export const api: InterviewApi = new HttpInterviewApi();

export type { InterviewApi, JoinResult, RoomHandle } from "./api";
export * from "./types";
