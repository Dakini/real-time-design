import { execFileSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, "..");
const COMPOSE_FILE = path.join(REPO_ROOT, "docker-compose.yaml");
const OVERLAY_FILE = path.join(__dirname, "docker-compose.e2e.yaml");
const PROJECT = "linewarmer-e2e";

export default async function globalTeardown(): Promise<void> {
  if (process.env["E2E_KEEP_STACK"] === "1") {
    const appPort = process.env["APP_PORT"] ?? "8100";
    console.log(`\nE2E_KEEP_STACK=1 — stack left up on http://localhost:${appPort}`);
    return;
  }

  execFileSync(
    "docker",
    ["compose", "-f", COMPOSE_FILE, "-f", OVERLAY_FILE, "-p", PROJECT, "down", "-v", "--remove-orphans"],
    { cwd: REPO_ROOT, env: process.env, stdio: "inherit", timeout: 120_000 },
  );
}
