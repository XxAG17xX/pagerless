"""Smoke check: connect to the logs MCP server in-process and call its tool.

Needs the Shop running (./dc.sh up -d) with OpenSearch on host port 9200 (compose.pagerless.yaml).
Run:  uv run mcp_servers/check_logs_mcp.py
"""

import asyncio
import json

from mcp import Client

from logs_mcp import mcp


async def main() -> None:
    async with Client(mcp) as client:
        names = [t.name for t in (await client.list_tools()).tools]
        assert names == ["logs_search"], names

        res = await client.call_tool("logs_search", {"limit": 5})
        assert not res.is_error, res.content[0].text  # e.g. OpenSearch not on port 9200
        records = json.loads(res.content[0].text)
        assert records and {"time", "service", "severity", "message", "trace_id"} <= records[0].keys(), records
        print(f"latest {len(records)} records, first: {records[0]}")

        res = await client.call_tool("logs_search", {"service": "cart", "minutes": 60, "limit": 3})
        records = json.loads(res.content[0].text)
        assert records and all(r["service"] == "cart" for r in records), records
        print(f"cart records: {len(records)}, first: {records[0]}")

        res = await client.call_tool("logs_search", {"severity": "error", "minutes": 60, "limit": 3})
        records = json.loads(res.content[0].text)
        print(f"error records: {len(records)}, first: {records[0] if records else None}")

        bad = await client.call_tool("logs_search", {"severity": "loud"})
        assert bad.is_error and "severity must be one of" in bad.content[0].text, bad.content[0].text
        print("bad severity error:", bad.content[0].text[:120])
    print("OK")


asyncio.run(main())
