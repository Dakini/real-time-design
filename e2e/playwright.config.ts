import { defineConfig, devices } from "@playwright/test";

const APP_PORT = process.env["APP_PORT"] ?? "8100";

export default defineConfig({
  testDir: "./tests",
  fullyParallel: true,
  retries: process.env["CI"] ? 2 : 0,
  reporter: "list",
  globalSetup: "./global-setup.ts",
  globalTeardown: "./global-teardown.ts",
  use: {
    baseURL: `http://127.0.0.1:${APP_PORT}`,
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
