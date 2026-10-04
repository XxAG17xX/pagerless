"""Break the Shop on purpose, wait for an alert, and write down the true cause (the answer key).

Usage:  uv run faults/inject.py payment-down
Writes runs/<time>_<fault>/truth.json, then fixes the Shop. The agent will never see truth.json.
"""

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

PROMETHEUS_URL = "http://localhost:9090"
ALERT_TIMEOUT_S = 600

# Each fault: how to break it, the true cause, and how to fix it. Container names come from the Shop.
FAULTS = {
    "payment-down": {
        "root_cause_service": "payment",
        "break": [["docker", "stop", "payment"]],
        # Stopping payment cascades into checkout and product-catalog (seen 2026-09-30), so the fix
        # restarts those too. ponytail: fixed list; read health checks if more faults cascade.
        "fix": [["docker", "start", "payment"], ["docker", "restart", "checkout", "product-catalog"]],
        "fix_text": "Start the payment service again.",
    },
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def firing_alerts() -> list[str]:
    alerts = httpx.get(f"{PROMETHEUS_URL}/api/v1/alerts", timeout=10).json()["data"]["alerts"]
    return [a["labels"]["alertname"] for a in alerts if a["state"] == "firing"]


def wait_for(condition, timeout_s: int) -> bool:
    end = time.monotonic() + timeout_s
    while time.monotonic() < end:
        if condition():
            return True
        time.sleep(15)
    return False


def main(name: str) -> None:
    fault = FAULTS[name]
    if firing_alerts():
        sys.exit(f"Alerts already firing ({firing_alerts()}); wait for a healthy Shop before injecting.")

    run_dir = Path("runs") / f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}_{name}"
    run_dir.mkdir(parents=True)
    truth = {"fault": name, "root_cause_service": fault["root_cause_service"], "fix": fault["fix_text"]}

    for cmd in fault["break"]:
        subprocess.run(cmd, check=True, capture_output=True)
    truth["injected_at"] = now()
    start = time.monotonic()
    print(f"{truth['injected_at']} broke the Shop ({name}); waiting for an alert...")

    fired = wait_for(lambda: bool(firing_alerts()), ALERT_TIMEOUT_S)
    truth["alerts"] = firing_alerts() if fired else []
    truth["seconds_to_alert"] = round(time.monotonic() - start) if fired else None
    print(f"alert: {truth['alerts'] or 'none within timeout'} after {truth['seconds_to_alert']} s")

    # ponytail: the agent runs here once it exists; for now we fix straight away.
    for cmd in fault["fix"]:
        subprocess.run(cmd, check=True, capture_output=True)
    truth["fixed_at"] = now()
    (run_dir / "truth.json").write_text(json.dumps(truth, indent=2))
    print(f"fixed; answer key written to {run_dir / 'truth.json'}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "payment-down")
