# on-call-engineer

Polls Grafana's alert API every minute; when an alert transitions to firing,
hands its details to a headless Claude Code agent that investigates, and - if
it finds a real bug - fixes and commits it (but doesn't push).

```
make on-call
# or
cd on-call-engineer && uv run python poll.py
```

## How it works

`poll.py` polls `GET /api/alertmanager/grafana/api/v2/alerts` on the
observability stack (see `../observability/`). Grafana only pushes an alert
into that endpoint once it's actually firing - a `for:` duration still
pending doesn't show up - so every alert seen here already represents
sustained, real impact.

For each alert whose fingerprint wasn't seen on the previous poll (i.e. it
just started firing, not one that's been firing for a while), it builds a
prompt from the alert's labels/annotations (service, environment, deployed
version, owner, severity, summary, and a link back to the alert rule),
instructing the agent to investigate, reproduce, fix the smallest correction
if it's a real bug, run the backend tests, and commit - or explain why and
leave the code alone if it's a false positive. It runs:

```
claude --print "<prompt>" --output-format json --allowedTools "<allowlist>"
```

from the repo root, so the agent can read and edit the actual code the alert
is about. The full prompt and the agent's response are written to
`incidents/<timestamp>-<fingerprint>.json` for review.

## Safety

This runs unattended, so there's no one to approve tool-permission prompts -
`CLAUDE_ALLOWED_TOOLS` is the only thing standing between the agent and the
repo, and anything outside it is simply denied rather than executed. The
default allows investigation (`Read`, `Grep`, `Glob`, read-only `git`),
`Edit`, running `make test-backend`, and `git add`/`git commit` - but not
`git push`. Publishing a fix is left as a deliberate, separate step (a human
reviewing the commit, or a future CI job) rather than shipping straight to
prod unattended.

## Configuration (env vars)

| Var | Default | Purpose |
| --- | --- | --- |
| `GRAFANA_URL` | `http://localhost:3000` | Base URL of the Grafana instance to poll |
| `GRAFANA_API_TOKEN` | unset | Bearer token, if anonymous Viewer access (the current default, see `../observability/docker-compose.yaml`) is ever turned off |
| `POLL_INTERVAL_SECONDS` | `60` | Poll interval |
| `REPO_DIR` | repo root | Working directory the agent runs in |
| `CLAUDE_ALLOWED_TOOLS` | set above | Passed to `claude --allowedTools` |
| `DRY_RUN` | unset | Set to `1` to log the prompt instead of invoking the agent |

Requires the `claude` CLI on `PATH` and an authenticated Claude Code session
(or `ANTHROPIC_API_KEY` set) to actually invoke the agent.

If your `claude` install has a shell hook that rewrites Bash commands (e.g. a
`git log` → `rtk git log` proxy), the default `CLAUDE_ALLOWED_TOOLS` patterns
like `Bash(git log:*)` won't match the rewritten command and those calls get
denied - including `git add`/`git commit`, which would silently block the
agent from ever committing a fix. Adjust the allowlist to match what your
hook actually invokes if so.
