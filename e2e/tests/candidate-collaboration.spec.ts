import { expect, test } from "@playwright/test";

const DEMO_OWNER_EMAIL = "jordan@linewarmer.io";

/**
 * Drives the real interviewer/candidate flow end to end against the compose
 * stack: no login form exists (see httpApi.ts), so "logging in" is the app
 * transparently establishing the seeded interviewer's session cookie on the
 * dashboard's first API call.
 */
test("candidate's canvas edit shows up live for the interviewer", async ({ browser, baseURL }) => {
  const interviewer = await browser.newContext();
  await interviewer.grantPermissions(["clipboard-read", "clipboard-write"], { origin: baseURL });
  const interviewerPage = await interviewer.newPage();

  // 1. Log in as the interviewer.
  const signIn = interviewerPage.waitForResponse(
    (res) => res.url().includes("/api/v1/auth/sign-in") && res.request().method() === "POST",
  );
  await interviewerPage.goto("/");
  expect((await (await signIn).json()).email).toBe(DEMO_OWNER_EMAIL);
  await expect(interviewerPage.getByRole("heading", { name: "Interviews" })).toBeVisible();

  // 2. Create an interview session.
  await interviewerPage.getByRole("link", { name: "New interview" }).click();
  await interviewerPage.getByLabel("Title").fill(`E2E collaboration ${Date.now()}`);
  await interviewerPage.getByLabel("Prompt").fill("Design something the e2e suite can draw on.");
  await interviewerPage.getByRole("button", { name: "Create interview" }).click();
  await interviewerPage.waitForURL(/\/room\//);
  await interviewerPage.getByRole("button", { name: "Start interview" }).click();

  // 3. Share the join link.
  await interviewerPage.getByRole("button", { name: "Share" }).click();
  await expect(interviewerPage.getByText("Candidate link copied")).toBeVisible();
  const joinUrl = await interviewerPage.evaluate(() => navigator.clipboard.readText());
  expect(joinUrl).toMatch(/\/join\//);

  // 4. Join from a separate client as the candidate.
  const candidate = await browser.newContext();
  const candidatePage = await candidate.newPage();
  await candidatePage.goto(joinUrl);
  await candidatePage.getByLabel("Display name").fill("Alex Candidate");
  await candidatePage.getByRole("button", { name: "Join interview" }).click();
  await candidatePage.waitForURL(/\/room\//);

  // 5. Change the canvas as the candidate: drop a "Cache" component.
  const candidateCanvas = candidatePage.getByRole("application", { name: "Interview canvas" });
  await candidatePage
    .locator('aside[aria-label="Component library"] button', { hasText: "Cache" })
    .first()
    .click();
  await candidateCanvas.click({ position: { x: 400, y: 300 } });
  await expect(candidateCanvas.getByText("Cache", { exact: true })).toBeVisible();

  // 6. Verify the interviewer sees the change over the shared realtime room.
  const interviewerCanvas = interviewerPage.getByRole("application", { name: "Interview canvas" });
  await expect(interviewerCanvas.getByText("Cache", { exact: true })).toBeVisible();

  await interviewer.close();
  await candidate.close();
});
