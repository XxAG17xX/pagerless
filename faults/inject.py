"""Break the Shop on purpose, wait for an alert, and write down the true cause (the answer key).

Usage:  uv run faults/inject.py payment-down
        uv run --env-file .env faults/inject.py payment-down --agent --repeats 4
Writes runs/<time>_<fault>/truth.json, then fixes the Shop. The agent never sees truth.json.
With --agent, the agent investigates N times while the fault is live (attempt_<i>/), and
score.json says whether each attempt named the true root-cause service.
"""

import argparse
import asyncio
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

PROMETHEUS_URL = "http://localhost:9090"
ALERT_TIMEOUT_S = 600
FLAG_FILE = Path("flagd/demo.flagd.json")  # our copy, mounted over flagd's by compose.pagerless.yaml


def run(cmd: list[str]) -> str:
    return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout


def set_flag(name: str, variant: str) -> None:
    """Switch one flag in our flag file; flagd polls the file and picks it up within seconds."""
    data = json.loads(FLAG_FILE.read_text())
    flag = data["flags"][name]
    if "targeting" in flag:  # productCatalogFailure: a rule picks one product; set that rule's variant
        flag["targeting"]["if"][1] = variant
    else:
        flag["defaultVariant"] = variant
    FLAG_FILE.write_text(json.dumps(data, indent=2) + "\n")


def flag_fault(flag: str, variant: str, cause: str, fix_text: str) -> dict:
    return {"root_cause_service": cause, "break": [lambda: set_flag(flag, variant)],
            "fix": [lambda: set_flag(flag, "off")], "fix_text": fix_text}


# Each fault: how to break it, the true cause, and how to fix it. A step is a docker command or a
# function. Container names come from the Shop.
FAULTS = {
    "payment-down": {
        "root_cause_service": "payment",
        "break": [["docker", "stop", "payment"]],
        # Stopping payment cascades into checkout and product-catalog (seen 2026-09-30), so the fix
        # restarts those too. ponytail: fixed list; read health checks if more faults cascade.
        "fix": [["docker", "start", "payment"], ["docker", "restart", "checkout", "product-catalog"]],
        "fix_text": "Start the payment service again.",
    },
    "payment-failure": flag_fault("paymentFailure", "100%", "payment",
                                  "Turn off the paymentFailure flag: payment rejects every charge."),
    "cart-failure": flag_fault("cartFailure", "100%", "cart",
                               "Turn off the cartFailure flag: cart fails every EmptyCart call."),
    "product-catalog-failure": flag_fault("productCatalogFailure", "on", "product-catalog",
                                          "Turn off the productCatalogFailure flag: product OLJCESPC7Z errors."),
    "currency-down": {
        "root_cause_service": "currency",
        "break": [["docker", "stop", "currency"]],
        "fix": [["docker", "start", "currency"]],
        "fix_text": "Start the currency service again.",
    },
    "shipping-frozen": {
        "root_cause_service": "shipping",
        "break": [["docker", "pause", "shipping"]],  # process frozen: calls hang instead of failing fast
        "fix": [["docker", "unpause", "shipping"]],
        "fix_text": "Unpause the shipping container.",
    },
    "recommendation-cpu-starved": {
        "root_cause_service": "recommendation",
        "break": [["docker", "update", "--cpus", "0.01", "recommendation"]],
        # "--cpus 0" does not clear a limit, so the fix sets it to every CPU Docker has.
        "fix": [lambda: run(["docker", "update", "--cpus", run(["docker", "info", "--format", "{{.NCPU}}"]).strip(),
                             "recommendation"])],
        "fix_text": "Remove the CPU limit on the recommendation container.",
    },
    "valkey-cart-down": {
        "root_cause_service": "valkey-cart",  # the cart's datastore; cart only reports the errors
        "break": [["docker", "stop", "valkey-cart"]],
        "fix": [["docker", "start", "valkey-cart"]],
        "fix_text": "Start the valkey-cart datastore again.",
    },
}


def run_steps(steps: list) -> None:
    for step in steps:
        step() if callable(step) else run(step)


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


def run_agent(run_dir: Path, truth: dict, repeats: int) -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from agent.investigate import investigate

    attempts = []
    for i in range(repeats):
        out = asyncio.run(investigate(run_dir / f"attempt_{i}"))
        answer = out["report"].get("root_cause_service", "")
        attempts.append({"attempt": i, "answer": answer,
                         "correct": answer.strip().lower() == truth["root_cause_service"].lower(),
                         **{k: out.get(k) for k in ("seconds", "tool_calls", "cost_usd")}})
        print(f"attempt {i}: {answer or out['report']} ({'right' if attempts[-1]['correct'] else 'wrong'})")
    score = {"fault": truth["fault"], "truth": truth["root_cause_service"], "attempts": attempts,
             "pass_all": all(a["correct"] for a in attempts), "baseline": truth.get("baseline")}
    (run_dir / "score.json").write_text(json.dumps(score, indent=2))


def main(name: str, agent: bool, repeats: int) -> None:
    fault = FAULTS[name]
    if firing_alerts():
        sys.exit(f"Alerts already firing ({firing_alerts()}); wait for a healthy Shop before injecting.")

    run_dir = Path("runs") / f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}_{name}"
    run_dir.mkdir(parents=True)
    truth = {"fault": name, "root_cause_service": fault["root_cause_service"], "fix": fault["fix_text"]}

    try:
        run_steps(fault["break"])
        truth["injected_at"] = now()
        start = time.monotonic()
        print(f"{truth['injected_at']} broke the Shop ({name}); waiting for an alert...")

        fired = wait_for(lambda: bool(firing_alerts()), ALERT_TIMEOUT_S)
        truth["alerts"] = firing_alerts() if fired else []
        truth["seconds_to_alert"] = round(time.monotonic() - start) if fired else None
        print(f"alert: {truth['alerts'] or 'none within timeout'} after {truth['seconds_to_alert']} s")
        if fired:  # the no-AI runbook answers at the same moment the agent starts
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            from baseline import diagnose
            b = diagnose()
            truth["baseline"] = {**b, "correct": b["root_cause_service"] == fault["root_cause_service"]}
            print(f"baseline: {b['root_cause_service'] or 'none'} ({b['rule']})")
        if agent and fired:
            run_agent(run_dir, truth, repeats)
    finally:  # fix the Shop even if the agent crashes or the run is interrupted
        run_steps(fault["fix"])
        truth["fixed_at"] = now()
        (run_dir / "truth.json").write_text(json.dumps(truth, indent=2))
        print(f"fixed; answer key written to {run_dir / 'truth.json'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Break the Shop, wait for an alert, fix it.")
    parser.add_argument("fault", nargs="?", default="payment-down", choices=FAULTS)
    parser.add_argument("--agent", action="store_true", help="run agent/investigate.py while the fault is live")
    parser.add_argument("--repeats", type=int, default=1, help="agent attempts per fault (default 1)")
    args = parser.parse_args()
    main(args.fault, args.agent, args.repeats)
