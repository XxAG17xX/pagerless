"""MCP server for incident memory: similar past incidents with their confirmed cause and fix.

Run by an MCP client over stdio:  uv run mcp_servers/memory_mcp.py
PAGERLESS_MEMORY_EXCLUDE_FAULT hides one fault type, so an evaluation can test the agent on a fault
it has never seen before instead of one it can simply look up.
"""

import json
import os
import sys
from pathlib import Path

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "memory"))
import store  # noqa: E402

mcp = MCPServer("memory_mcp")
READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)


@mcp.tool(name="memory_search_incidents", annotations=READ_ONLY)
def search_incidents(symptoms: str, k: int = 3) -> str:
    """Find past incidents with similar symptoms, with the root cause a human confirmed and the fix.

    Describe what you see: firing alerts, failing or slow services, error messages. A past incident
    is a hint, not evidence: the same symptoms can have a different cause, so confirm any match
    against live metrics, traces or logs before relying on it. Returns JSON, at most 5 incidents.
    """
    exclude = os.environ.get("PAGERLESS_MEMORY_EXCLUDE_FAULT") or None
    return json.dumps(store.search(store.connect(), symptoms, min(k, 5), exclude))


if __name__ == "__main__":
    mcp.run()  # stdio
