/**
 * Brings up the real docker compose stack (app + Postgres) once for the whole
 * run, the same way `integration/conftest.py` does for the Python suite. The
 * app serves the built frontend itself (see ../Dockerfile), so Playwright
 * drives the actual production bundle rather than a dev server.
 *
 * Env overrides:
 *   APP_PORT        host port the app is published on (default 8100)
 *   PG_PORT         host port Postgres is published on (default 55432)
 *   E2E_KEEP_STACK  leave the stack running after the run, for debugging
 */
import { execFileSync } from "node:child_process";
import net from "node:net";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, "..");
const COMPOSE_FILE = path.join(REPO_ROOT, "docker-compose.yaml");
const OVERLAY_FILE = path.join(__dirname, "docker-compose.e2e.yaml");
const PROJECT = "linewarmer-e2e";

const APP_PORT = process.env["APP_PORT"] ?? "8100";
const PG_PORT = process.env["PG_PORT"] ?? "55432";

// `up --build` runs `npm ci` plus a Vite build on a cold cache.
const BUILD_TIMEOUT_MS = 900_000;

function compose(args: string[], timeout = 120_000): void {
  execFileSync(
    "docker",
    ["compose", "-f", COMPOSE_FILE, "-f", OVERLAY_FILE, "-p", PROJECT, ...args],
    {
      cwd: REPO_ROOT,
      env: { ...process.env, APP_PORT, PG_PORT },
      stdio: "inherit",
      timeout,
    },
  );
}

function portIsFree(port: number): Promise<boolean> {
  return new Promise((resolve) => {
    const socket = net.connect({ port, host: "127.0.0.1" });
    socket.once("connect", () => {
      socket.destroy();
      resolve(false);
    });
    socket.once("error", () => resolve(true));
  });
}

export default async function globalSetup(): Promise<void> {
  try {
    execFileSync("docker", ["info"], { stdio: "ignore" });
  } catch {
    throw new Error("docker is not available — start Docker Desktop before running the e2e suite");
  }

  // A previous aborted run may have left containers behind; start clean so
  // the seeded-owner assumptions the tests make (see seed.py) hold. Done
  // before the port check so our own leftovers free the port rather than
  // fail it.
  compose(["down", "-v", "--remove-orphans"]);

  if (!(await portIsFree(Number(APP_PORT)))) {
    throw new Error(
      `port ${APP_PORT} is already in use — stop the dev stack (\`make down\`) or run with APP_PORT=<other port>`,
    );
  }

  compose(["up", "--build", "-d", "--wait", "--wait-timeout", "180"], BUILD_TIMEOUT_MS);
}
