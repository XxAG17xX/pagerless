"""Rules-based baseline: a fixed runbook with no AI, scored on the same faults as the agent.

The runbook, in order:
  1. A backend service that had traffic 30 minutes ago and has none now is down: blame it.
  2. Otherwise blame the backend service with the highest error ratio, if above 5%.
  3. Otherwise blame the backend service with the highest p95 latency, if above 1 second.
Usage: uv run faults/baseline.py   (prints the answer and the rule that produced it)
"""

import json

import httpx

PROMETHEUS_URL = "http://localhost:9090"
SKIP = "frontend|frontend-proxy|frontend-web|load-generator|flagd|telemetry-docs"  # entry points and infra
SERVER = f'span_kind="SPAN_KIND_SERVER", service_name!~"{SKIP}"'


def query(promql: str) -> dict[str, float]:
    result = httpx.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": promql}, timeout=10).json()["data"]["result"]
    return {r["metric"].get("service_name", ""): float(r["value"][1]) for r in result}


def diagnose() -> dict:
    before = query(f"sum by (service_name) (rate(traces_span_metrics_calls_total{{{SERVER}}}[5m] offset 30m))")
    now = query(f"sum by (service_name) (rate(traces_span_metrics_calls_total{{{SERVER}}}[5m]))")
    gone = [s for s, r in before.items() if r > 0 and now.get(s, 0) == 0]
    if gone:
        return {"root_cause_service": sorted(gone)[0], "rule": "1: traffic stopped"}

    errors = query(f'sum by (service_name) (rate(traces_span_metrics_calls_total{{{SERVER}, status_code="STATUS_CODE_ERROR"}}[5m]))'
                   f" / sum by (service_name) (rate(traces_span_metrics_calls_total{{{SERVER}}}[5m]))")
    worst = max(errors.items(), key=lambda kv: kv[1], default=("", 0))
    if worst[1] > 0.05:
        return {"root_cause_service": worst[0], "rule": f"2: error ratio {worst[1]:.0%}"}

    p95 = query(f"histogram_quantile(0.95, sum by (service_name, le) "
                f"(rate(traces_span_metrics_duration_milliseconds_bucket{{{SERVER}}}[5m])))")
    slowest = max(((s, v) for s, v in p95.items() if v == v), key=lambda kv: kv[1], default=("", 0))  # v == v drops NaN
    if slowest[1] > 1000:
        return {"root_cause_service": slowest[0], "rule": f"3: p95 {slowest[1]:.0f} ms"}
    return {"root_cause_service": "", "rule": "no rule matched"}


if __name__ == "__main__":
    print(json.dumps(diagnose()))
