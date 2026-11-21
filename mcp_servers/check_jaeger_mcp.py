"""Smoke check: connect to the Jaeger MCP server in-process and call each tool.

Needs the Shop running (./dc.sh up -d). Run:  uv run mcp_servers/check_jaeger_mcp.py
"""

import asyncio
import json

from mcp import Client

from jaeger_mcp import mcp


async def main() -> None:
    async with Client(mcp) as client:
        names = [t.name for t in (await client.list_tools()).tools]
        assert names == ["jaeger_list_services", "jaeger_find_traces", "jaeger_get_trace"], names

        res = await client.call_tool("jaeger_list_services", {})
        assert not res.is_error, res.content[0].text  # e.g. Shop not running: ./dc.sh up -d
        services = json.loads(res.content[0].text)
        assert "frontend" in services, services
        print(f"services: {services}")

        res = await client.call_tool("jaeger_find_traces", {"service": "frontend", "limit": 5})
        traces = json.loads(res.content[0].text)
        assert traces and {"trace_id", "root", "duration_ms", "spans", "error_services"} <= traces[0].keys(), traces
        print(f"found {len(traces)} traces, first: {traces[0]}")

        res = await client.call_tool("jaeger_get_trace", {"trace_id": max(traces, key=lambda t: t["spans"])["trace_id"]})
        trace = json.loads(res.content[0].text)
        assert trace["spans_shown"] <= 40 and trace["spans"][0]["depth"] == 0, trace
        print(f"trace has {trace['spans_total']} spans, showing {trace['spans_shown']}, first: {trace['spans'][0]}")
        print(f"trace JSON size: {len(res.content[0].text)} chars")

        bad = await client.call_tool("jaeger_get_trace", {"trace_id": "not-a-trace"})
        assert bad.is_error and "Jaeger rejected" in bad.content[0].text, bad.content[0].text
        print("bad trace id error:", bad.content[0].text[:120])
    print("OK")


asyncio.run(main())
