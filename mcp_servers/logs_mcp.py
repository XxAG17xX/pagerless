"""MCP server that lets an agent search the Shop's recent logs, stored in OpenSearch.

Run by an MCP client over stdio:  uv run mcp_servers/logs_mcp.py
The tool docstrings below are what the model reads to decide which tool to call and how.
"""

import json
import os

import httpx
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

# Fixed host port set in compose.pagerless.yaml; the demo runs OpenSearch without auth.
OPENSEARCH_URL = os.environ.get("OPENSEARCH_URL", "http://localhost:9200")
INDEX = "otel-logs-*"  # the collector writes one index per day, e.g. otel-logs-2026-11-21
MAX_RECORDS = 50  # ponytail: hard cap on records returned, add paging if the agent needs more
MAX_MSG = 300  # characters kept from each message
# OpenTelemetry severity numbers: each level's lowest value.
LEVELS = {"debug": 5, "info": 9, "warn": 13, "error": 17, "fatal": 21}

mcp = MCPServer("logs_mcp")
READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)


@mcp.tool(name="logs_search", annotations=READ_ONLY)
def search(service: str | None = None, contains: str | None = None, severity: str | None = None, minutes: int = 15, limit: int = 20) -> str:
    """Search the Shop's recent log records, newest first.

    service: exact service name, e.g. "cart", "checkout", "payment", "frontend", "frontend-proxy".
    contains: a word or phrase that must appear in the message or exception (case-insensitive).
    severity: minimum level, one of "debug", "info", "warn", "error", "fatal". "error" is the usual
    choice in an investigation. frontend-proxy access logs have no severity, so any severity filter
    hides them; search those with contains, e.g. contains=" 500 ".
    Returns JSON: a list of {"time", "service", "severity", "message", "trace_id"}, at most 50,
    plus "exception" when one was logged. Pass a trace_id to jaeger_get_trace to see that request.
    """
    filters = [{"range": {"@timestamp": {"gte": f"now-{int(minutes)}m"}}}]
    if service:
        filters.append({"term": {"resource.service.name.keyword": service}})
    if contains:
        filters.append({"multi_match": {"query": contains, "type": "phrase", "fields": ["body", "attributes.exception.message"]}})
    if severity:
        if severity.lower() not in LEVELS:
            raise ToolError(f"severity must be one of {list(LEVELS)}, got {severity!r}")
        filters.append({"range": {"severity.number": {"gte": LEVELS[severity.lower()]}}})
    query = {
        "size": min(limit, MAX_RECORDS),
        "sort": [{"@timestamp": "desc"}],
        "query": {"bool": {"filter": filters}},
        "_source": ["@timestamp", "resource.service.name", "severity.text", "body", "traceId", "attributes.exception.message"],
    }
    try:
        body = httpx.post(f"{OPENSEARCH_URL}/{INDEX}/_search", json=query, timeout=10).json()
    except (httpx.HTTPError, ValueError) as e:
        raise ToolError(f"OpenSearch unreachable at {OPENSEARCH_URL}: {e}") from e
    if "error" in body:
        raise ToolError(f"OpenSearch rejected the search: {body['error'].get('reason', body['error'])}")

    out = []
    for hit in body["hits"]["hits"]:
        src = hit["_source"]
        row = {
            "time": src.get("@timestamp"),
            "service": src.get("resource", {}).get("service.name"),
            "severity": src.get("severity", {}).get("text"),
            "message": str(src.get("body", "")).strip()[:MAX_MSG],
            "trace_id": src.get("traceId"),
        }
        if exc := src.get("attributes", {}).get("exception.message"):
            row["exception"] = str(exc)[:MAX_MSG]
        out.append(row)
    return json.dumps(out)


if __name__ == "__main__":
    mcp.run()  # stdio
