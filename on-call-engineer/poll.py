"""Polls Grafana's alert API and hands newly-firing alerts to a headless
Claude Code agent, which investigates and - if it finds a real bug - fixes
and commits it.

Grafana's alerting engine only pushes an alert into its built-in
Alertmanager once it's actually firing (i.e. its `for:` duration has
elapsed) - a "pending" alert never shows up here. So GET .../v2/alerts with
status.state == "active" is exactly "alerts with real, sustained impact
right now", which is what we want to hand to the agent.

Usage: uv run python poll.py
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

GRAFANA_URL = os.environ.get("GRAFANA_URL", "http://localhost:3000").rstrip("/")
GRAFANA_API_TOKEN = os.environ.get("GRAFANA_API_TOKEN")  # unset: anonymous Viewer access, see observability/docker-compose.yaml
POLL_INTERVAL_SECONDS = float(os.environ.get("POLL_INTERVAL_SECONDS", "60"))

# Defaults to the repo root (this directory's parent) so the agent runs with
# the codebase the alerts are about as its working directory.
REPO_DIR = Path(os.environ.get("REPO_DIR", Path(__file__).resolve().parent.parent))

INCIDENTS_DIR = Path(__file__).resolve().parent / "incidents"

# The agent is allowed to investigate, edit code, run the backend test suite,
# and commit - but not push. Publishing a fix is a separate, deliberate step
# (left to a human, or to a future CI job) - this cron job's job is to leave
# a reviewable commit, not to ship straight to prod unsupervised.
CLAUDE_ALLOWED_TOOLS = os.environ.get(
    "CLAUDE_ALLOWED_TOOLS",
    "Read Grep Glob Edit "
    "Bash(git log:*) Bash(git show:*) Bash(git diff:*) Bash(git blame:*) "
    "Bash(git add:*) Bash(git commit:*) "
    "Bash(make test-backend:*)",
)

DRY_RUN = os.environ.get("DRY_RUN") == "1"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("on-call-engineer")


def fetch_active_alerts() -> list[dict]:
    headers = {"Authorization": f"Bearer {GRAFANA_API_TOKEN}"} if GRAFANA_API_TOKEN else {}
    url = f"{GRAFANA_URL}/api/alertmanager/grafana/api/v2/alerts"
    response = httpx.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    return [alert for alert in response.json() if alert.get("status", {}).get("state") == "active"]


def build_prompt(alert: dict) -> str:
    labels = alert.get("labels", {})
    annotations = alert.get("annotations", {})
    lines = [
        "You are the on-call engineer for this repository. An alert just fired.",
        "",
        "Investigate the root cause. Read the code and reproduce the failure.",
        "If you find a real bug, make the smallest correction, run the backend tests",
        "(`make test-backend`), and commit the fix with a clear message.",
        "",
        "If the alert is a false positive, explain why and do not change the code.",
        "",
        f"Alert: {labels.get('alertname', '(unnamed)')}",
        f"Severity: {labels.get('severity', 'unknown')}",
        f"Service: {labels.get('service', 'unknown')}",
        f"Environment: {labels.get('deployment_environment', 'unknown')}",
        f"Deployed version: {labels.get('service_version', 'unknown')}",
        f"Owner: {labels.get('owner', 'unassigned')}",
        f"Firing since: {alert.get('startsAt', 'unknown')}",
    ]
    if annotations.get("summary"):
        lines.append(f"Summary: {annotations['summary']}")
    if alert.get("generatorURL"):
        lines.append(f"Alert rule: {alert['generatorURL']}")
    other_labels = {k: v for k, v in labels.items() if k not in {"alertname", "severity", "service", "deployment_environment", "service_version", "owner"}}
    if other_labels:
        lines.append(f"Other labels: {json.dumps(other_labels)}")
    return "\n".join(lines)


def invoke_agent(alert: dict) -> None:
    prompt = build_prompt(alert)
    fingerprint = alert.get("fingerprint", "unknown")
    log.info("Alert fired (%s): %s", fingerprint, alert.get("labels", {}).get("alertname"))

    if DRY_RUN:
        log.info("DRY_RUN=1, not invoking agent. Prompt:\n%s", prompt)
        return

    result = subprocess.run(
        [
            "claude",
            "--print",
            prompt,
            "--output-format",
            "json",
            "--allowedTools",
            CLAUDE_ALLOWED_TOOLS,
        ],
        cwd=REPO_DIR,
        capture_output=True,
        text=True,
    )

    INCIDENTS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    record_path = INCIDENTS_DIR / f"{timestamp}-{fingerprint}.json"
    record_path.write_text(
        json.dumps(
            {
                "alert": alert,
                "prompt": prompt,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            },
            indent=2,
        )
    )
    log.info("Agent finished (exit %d), transcript: %s", result.returncode, record_path)


def main() -> None:
    log.info(
        "Polling %s every %ds (repo=%s, dry_run=%s)", GRAFANA_URL, POLL_INTERVAL_SECONDS, REPO_DIR, DRY_RUN
    )
    seen_fingerprints: set[str] = set()

    while True:
        try:
            alerts = fetch_active_alerts()
        except httpx.HTTPError as exc:
            log.warning("Failed to poll %s: %s", GRAFANA_URL, exc)
            time.sleep(POLL_INTERVAL_SECONDS)
            continue

        current_fingerprints = {alert["fingerprint"] for alert in alerts}
        newly_firing = [alert for alert in alerts if alert["fingerprint"] not in seen_fingerprints]

        for alert in newly_firing:
            invoke_agent(alert)

        # Replace (not union) so an alert that resolves and later fires again
        # is treated as new, and re-triaged, rather than being suppressed
        # forever after its first firing.
        seen_fingerprints = current_fingerprints

        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
