"""Smoke check: connect to the Prometheus MCP server in-process and call both tools.

Needs the Shop running (./dc.sh up -d). Run:  uv run mcp_servers/check_prometheus_mcp.py
"""

import asyncio
import json

from mcp import Client

from prometheus_mcp import mcp


async def main() -> None:
    async with Client(mcp) as client:
        names = [t.name for t in (await client.list_tools()).tools]
        assert names == ["prometheus_firing_alerts", "prometheus_query"], names

        res = await client.call_tool("prometheus_firing_alerts", {})
        assert not res.is_error, res.content[0].text  # e.g. Prometheus not running: ./dc.sh up -d
        alerts = json.loads(res.content[0].text)
        assert isinstance(alerts, list), alerts
        print(f"firing/pending alerts: {len(alerts)}")

        result = await client.call_tool("prometheus_query", {"promql": "sum by (service_name) (rate(traces_span_metrics_calls_total[5m]))"})
        series = json.loads(result.content[0].text)
        assert series and "labels" in series[0] and "value" in series[0], series
        print(f"query returned {len(series)} series, first: {series[0]}")

        bad = await client.call_tool("prometheus_query", {"promql": "sum(("})
        assert bad.is_error and "parse error" in bad.content[0].text, bad.content[0].text
        print("broken query error:", bad.content[0].text[:120])
    print("OK")


asyncio.run(main())
