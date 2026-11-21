"""MCP server that lets an agent read the Shop's traces from Jaeger: find traces, then open one.

Run by an MCP client over stdio:  uv run mcp_servers/jaeger_mcp.py
The tool docstrings below are what the model reads to decide which tool to call and how.
"""

import json
import os
import time

import httpx
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

# Jaeger's query API, reached through the Shop's frontend-proxy.
JAEGER_URL = os.environ.get("JAEGER_URL", "http://localhost:8080/jaeger/ui/api")
MAX_TRACES = 20  # ponytail: hard cap on traces per search, add paging if the agent needs more
MAX_SPANS = 40  # ponytail: hard cap on spans per trace; error spans first, then the slowest
MAX_MSG = 200  # characters kept from an error message

mcp = MCPServer("jaeger_mcp")
READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)


def _get(path: str, params: dict | None = None):
    """GET a Jaeger query API path and return its `data` field; failures raise ToolError for the model."""
    try:
        body = httpx.get(f"{JAEGER_URL}{path}", params=params, timeout=10).json()
    except (httpx.HTTPError, ValueError) as e:
        raise ToolError(f"Jaeger unreachable at {JAEGER_URL}: {e}") from e
    if body.get("errors"):
        raise ToolError(f"Jaeger rejected the request: {body['errors'][0].get('msg')}")
    return body["data"]


def _tags(span: dict) -> dict:
    return {t["key"]: t["value"] for t in span["tags"]}


def _is_error(span: dict) -> bool:
    tags = _tags(span)
    return tags.get("error") is True or tags.get("otel.status_code") == "ERROR"


def _error_message(span: dict) -> str | None:
    """The best human-readable reason a span failed: a recorded exception, else the status tags."""
    for log in span["logs"]:
        for f in log["fields"]:
            if f["key"] == "exception.message":
                return str(f["value"])[:MAX_MSG]
    tags = _tags(span)
    for key in ("otel.status_description", "grpc.error_message", "error.type", "http.status_code"):
        if key in tags:
            return f"{key}={tags[key]}"[:MAX_MSG]
    return None


def _parent(span: dict) -> str | None:
    return next((r["spanID"] for r in span["references"] if r["refType"] == "CHILD_OF"), None)


def _root(trace: dict) -> dict:
    """The earliest span whose parent is not in this trace (Jaeger may hold a partial trace)."""
    ids = {s["spanID"] for s in trace["spans"]}
    roots = [s for s in trace["spans"] if _parent(s) not in ids] or trace["spans"]
    return min(roots, key=lambda s: s["startTime"])


def _service(trace: dict, span: dict) -> str:
    return trace["processes"][span["processID"]]["serviceName"]


@mcp.tool(name="jaeger_list_services", annotations=READ_ONLY)
def list_services() -> str:
    """List the service names Jaeger has traces for, as a JSON list of strings.

    Call this when unsure of a service's exact name for jaeger_find_traces.
    A service missing from this list has sent no traces recently, which may itself be a clue.
    """
    return json.dumps(sorted(_get("/services") or []))


@mcp.tool(name="jaeger_find_traces", annotations=READ_ONLY)
def find_traces(service: str, operation: str | None = None, errors_only: bool = False, lookback_minutes: int = 15, limit: int = 10) -> str:
    """Search recent traces that touch a service, newest first, and summarise each one.

    service: exact service name, e.g. "frontend", "checkout", "cart", "payment" (see jaeger_list_services).
    operation: optional exact span name, e.g. "oteldemo.CheckoutService/PlaceOrder".
    errors_only: true keeps only traces containing at least one error span. Use it to find failures.
    Returns JSON: a list of {"trace_id", "root" ("service: operation"), "duration_ms", "spans",
    "error_services" (services with error spans, empty if none)}, at most 20 traces.
    Then call jaeger_get_trace with a trace_id to see where it failed or was slow.
    """
    now_us = int(time.time() * 1_000_000)
    params = {"service": service, "start": now_us - lookback_minutes * 60_000_000, "end": now_us, "limit": min(limit, MAX_TRACES)}
    if operation:
        params["operation"] = operation
    if errors_only:
        params["tags"] = json.dumps({"error": "true"})
    out = []
    for trace in _get("/traces", params) or []:
        root = _root(trace)
        errors = sorted({_service(trace, s) for s in trace["spans"] if _is_error(s)})
        out.append({"trace_id": trace["traceID"], "root": f"{_service(trace, root)}: {root['operationName']}", "duration_ms": round(root["duration"] / 1000, 1), "spans": len(trace["spans"]), "error_services": errors})
    return json.dumps(out)


@mcp.tool(name="jaeger_get_trace", annotations=READ_ONLY)
def get_trace(trace_id: str) -> str:
    """Open one trace by its id (32 hex characters, from jaeger_find_traces) and list its spans.

    Long traces are trimmed to 40 spans: every error span is kept, then the slowest ones.
    Returns JSON {"trace_id", "spans_total", "spans_shown", "spans": [...]}, spans in start order, each
    {"start_ms" (offset from trace start), "depth" (0 = root), "service", "operation", "duration_ms"},
    plus "error": true and, when known, "error_message" on failed spans. The deepest error span is usually
    closest to the root cause; a parent's error often just repeats its child's.
    """
    trace = _get(f"/traces/{trace_id}")[0]
    spans = trace["spans"]
    by_id = {s["spanID"]: s for s in spans}

    def depth(s: dict) -> int:
        d = 0
        while (p := _parent(s)) in by_id and d < 100:  # d guards against a reference loop
            s, d = by_id[p], d + 1
        return d

    kept = sorted(spans, key=lambda s: (not _is_error(s), -s["duration"]))[:MAX_SPANS]
    t0 = min(s["startTime"] for s in spans)
    out = []
    for s in sorted(kept, key=lambda s: s["startTime"]):
        row = {"start_ms": round((s["startTime"] - t0) / 1000, 1), "depth": depth(s), "service": _service(trace, s), "operation": s["operationName"], "duration_ms": round(s["duration"] / 1000, 1)}
        if _is_error(s):
            row["error"] = True
            if msg := _error_message(s):
                row["error_message"] = msg
        out.append(row)
    return json.dumps({"trace_id": trace["traceID"], "spans_total": len(spans), "spans_shown": len(out), "spans": out})


if __name__ == "__main__":
    mcp.run()  # stdio
