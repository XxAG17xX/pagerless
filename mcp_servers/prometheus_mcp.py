"""MCP server that lets an agent read the Shop's Prometheus: firing alerts and PromQL queries.

Run by an MCP client over stdio:  uv run mcp_servers/prometheus_mcp.py
The tool docstrings below are what the model reads to decide which tool to call and how.
"""

import json
import os

import httpx
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", "http://localhost:9090")
MAX_SERIES = 30  # ponytail: hard cap on series returned, add paging if the agent needs more

mcp = MCPServer("prometheus_mcp")
READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)


def _get(path: str, params: dict | None = None) -> dict:
    """GET a Prometheus HTTP API path and return its `data` field.

    Failures raise ToolError, whose message the model reads (any other exception reaches it only
    as "Error executing tool"), so a bad PromQL query comes back with Prometheus's own reason.
    """
    try:
        body = httpx.get(f"{PROMETHEUS_URL}{path}", params=params, timeout=10).json()
    except httpx.HTTPError as e:
        raise ToolError(f"Prometheus unreachable at {PROMETHEUS_URL}: {e}") from e
    if body.get("status") != "success":
        raise ToolError(f"Prometheus rejected the request: {body.get('errorType')}: {body.get('error')}")
    return body["data"]


@mcp.tool(name="prometheus_firing_alerts", annotations=READ_ONLY)
def firing_alerts() -> str:
    """List alerts that are currently pending or firing, with their labels, summary and start time.

    Call this first in an investigation: it says what is wrong right now.
    Returns a JSON list; an empty list means nothing is alerting.
    """
    # TODO(Kartik): call _get("/api/v1/alerts"). Its result has a key "alerts": a list of dicts,
    # each with "labels" (includes "alertname"), "annotations" (includes "summary"), "state"
    # ("pending" or "firing") and "activeAt". Return json.dumps of a list with just those four
    # things per alert, so the model isn't flooded with noise.
    alerts = _get("/api/v1/alerts")["alerts"]
    return json.dumps([{"alertname": a["labels"]["alertname"], "state": a["state"], "summary": a["annotations"].get("summary"), "active_at": a["activeAt"]} for a in alerts])


@mcp.tool(name="prometheus_query", annotations=READ_ONLY)
def query(promql: str) -> str:
    """Run an instant PromQL query against the Shop's Prometheus and return the matching series.

    Most useful metric: traces_span_metrics_calls_total, with labels service_name, span_name and
    status_code (STATUS_CODE_ERROR or STATUS_CODE_UNSET). Wrap counters in rate(...[5m]).
    Example: sum by (service_name) (rate(traces_span_metrics_calls_total{status_code="STATUS_CODE_ERROR"}[5m]))
    Returns JSON: a list of {"labels": {...}, "value": "..."}, at most 30 series.
    """
    # TODO(Kartik): call _get("/api/v1/query", {"query": promql}). Its result has a key "result":
    # a list of dicts, each with "metric" (the labels) and "value" ([timestamp, "number"]).
    # Return json.dumps of the first MAX_SERIES as {"labels": ..., "value": <the number string>}.
    result = _get("/api/v1/query",{"query": promql})["result"]
    return json.dumps([{"labels": r["metric"], "value": r["value"][1]} for r in result[:MAX_SERIES]])


if __name__ == "__main__":
    mcp.run()  # stdio
