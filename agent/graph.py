"""The Pagerless agent as a LangGraph graph: same tools and prompt as investigate.py, plus two things
the plain loop cannot do:
  - checkpoints: every step is saved in Postgres, so a crashed investigation resumes where it stopped
  - a human gate: the graph pauses (interrupt) on the report and waits for a person to approve the fix

    think --tool calls--> act --> think ... --report--> approve (pauses for a human) --> END

Usage:
  uv run --env-file .env agent/graph.py runs/manual            # new investigation, asks y/n at the end
  uv run --env-file .env agent/graph.py runs/manual --thread T # resume thread T after a crash
  uv run --env-file .env agent/graph.py runs/manual --decision skip   # non-interactive (exam runs)
"""

import argparse
import asyncio
import importlib.util
import json
import operator
import os
import sys
import time
import uuid
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Annotated, TypedDict

import anthropic
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from mcp import Client

sys.path.insert(0, str(Path(__file__).resolve().parent))
from investigate import MAX_STEPS, MODEL, PRICES, REPORT_SCHEMA, SERVERS, SYSTEM  # one prompt, two agents

DB_URL = os.environ.get("PAGERLESS_DB", "postgresql://pagerless:pagerless@localhost:5433/pagerless")


class State(TypedDict):
    messages: Annotated[list, operator.add]  # Anthropic-format messages, appended by each node
    steps: Annotated[list, operator.add]     # tool calls made, for the trace
    usage: Annotated[list, operator.add]     # one usage dict per model call
    report: dict
    decision: str


def build(client: anthropic.AsyncAnthropic, tools: list, owner: dict):
    async def think(state: State) -> dict:
        r = await client.messages.create(
            model=MODEL, max_tokens=16000, system=SYSTEM, tools=tools, messages=state["messages"],
            cache_control={"type": "ephemeral"},
            output_config={"format": {"type": "json_schema", "schema": REPORT_SCHEMA}},
        )
        u = {"input": r.usage.input_tokens, "output": r.usage.output_tokens,
             "cache_read": r.usage.cache_read_input_tokens or 0, "cache_write": r.usage.cache_creation_input_tokens or 0}
        # Blocks go back to the API unchanged (thinking blocks included), as plain dicts so Postgres can store them.
        update = {"messages": [{"role": "assistant", "content": [b.model_dump(exclude_none=True) for b in r.content]}],
                  "usage": [u]}
        if r.stop_reason != "tool_use":
            text = next((b.text for b in r.content if b.type == "text"), "{}")
            update["report"] = json.loads(text) if r.stop_reason == "end_turn" else {"error": r.stop_reason}
        return update

    async def act(state: State) -> dict:
        calls = [b for b in state["messages"][-1]["content"] if b["type"] == "tool_use"]
        results, steps = [], []
        for c in calls:
            res = await owner[c["name"]].call_tool(c["name"], c["input"])
            out = res.content[0].text if res.content else ""
            steps.append({"tool": c["name"], "input": c["input"], "is_error": res.is_error, "output": out[:2000]})
            results.append({"type": "tool_result", "tool_use_id": c["id"], "content": out, "is_error": bool(res.is_error)})
        return {"messages": [{"role": "user", "content": results}], "steps": steps}

    def approve(state: State) -> dict:
        # Pauses the graph; the run resumes when someone answers with Command(resume=...).
        return {"decision": interrupt({"report": state.get("report", {})})}

    def route(state: State) -> str:
        if state.get("report"):
            return "approve"
        if len(state["steps"]) >= MAX_STEPS * 3:  # ponytail: same budget idea as the plain loop's step cap
            return "approve"
        return "act"

    g = StateGraph(State)
    g.add_node("think", think)
    g.add_node("act", act)
    g.add_node("approve", approve)
    g.add_edge(START, "think")
    g.add_conditional_edges("think", route, ["act", "approve"])
    g.add_edge("act", "think")
    g.add_edge("approve", END)
    return g


def load_server(path: str):
    """Import an MCP server module and return its server object.

    Windows only: psycopg's async mode needs the selector event loop, which cannot start subprocesses,
    so the graph talks to the same MCP servers in-process (full MCP protocol, in-memory transport)
    instead of over stdio like investigate.py does.
    """
    spec = importlib.util.spec_from_file_location(Path(path).stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.mcp


def ask(report: dict) -> str:
    print(json.dumps(report, indent=2))
    answer = input(f"\nApply this fix? {report.get('suggested_fix', '')}\n[y = approve, n = reject] ").strip().lower()
    return "approved" if answer == "y" else "rejected"


async def investigate(run_dir: Path, thread: str | None = None, decision: str | None = None) -> dict:
    thread = thread or uuid.uuid4().hex
    config = {"configurable": {"thread_id": thread}, "recursion_limit": 2 * MAX_STEPS + 5}
    started = time.monotonic()
    async with AsyncExitStack() as stack:
        sessions = [await stack.enter_async_context(Client(load_server(s))) for s in SERVERS]
        owner, tools = {}, []
        for s in sessions:
            for t in (await s.list_tools()).tools:
                owner[t.name] = s
                tools.append({"name": t.name, "description": t.description, "input_schema": t.input_schema})
        saver = await stack.enter_async_context(AsyncPostgresSaver.from_conn_string(DB_URL))
        await saver.setup()  # creates the checkpoint tables once; a no-op after that
        client = await stack.enter_async_context(anthropic.AsyncAnthropic())
        graph = build(client, tools, owner).compile(checkpointer=saver)

        resuming = (await graph.aget_state(config)).next
        first = None if resuming else {"messages": [{"role": "user", "content": "An alert fired. Investigate and report the root cause."}],
                                       "steps": [], "usage": [], "report": {}, "decision": ""}
        print(f"thread {thread}: {'resuming at ' + str(resuming) if resuming else 'new investigation'}")
        await graph.ainvoke(first, config)
        state = await graph.aget_state(config)
        if state.next == ("approve",):  # paused at the human gate
            report = state.tasks[0].interrupts[0].value["report"]
            await graph.ainvoke(Command(resume=decision or ask(report)), config)
        values = (await graph.aget_state(config)).values

    usage = {k: sum(u[k] for u in values["usage"]) for k in ("input", "output", "cache_read", "cache_write")}
    p_in, p_out, p_cache = PRICES.get(MODEL, (0, 0, 0))
    cost = (usage["input"] * p_in + usage["output"] * p_out + usage["cache_read"] * p_cache
            + usage["cache_write"] * p_in * 1.25) / 1e6
    report = values.get("report") or {"error": "no report"}
    trace = {"model": MODEL, "engine": "langgraph", "thread": thread, "decision": values.get("decision"),
             "seconds": round(time.monotonic() - started, 1), "tool_calls": len(values["steps"]),
             "usage": usage, "cost_usd": round(cost, 4), "steps": values["steps"]}
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "report.json").write_text(json.dumps(report, indent=2))
    (run_dir / "trace.json").write_text(json.dumps(trace, indent=2))
    return {"report": report, **{k: trace[k] for k in ("seconds", "tool_calls", "cost_usd", "decision", "thread")}}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Run the LangGraph version of the Pagerless agent.")
    p.add_argument("run_dir", nargs="?", default="runs/manual_graph")
    p.add_argument("--thread", help="resume this thread id (printed at the start of every run)")
    p.add_argument("--decision", choices=["approved", "rejected", "skip"], help="answer the human gate without asking")
    a = p.parse_args()
    loop = asyncio.SelectorEventLoop if sys.platform == "win32" else None  # psycopg async needs it on Windows
    out = asyncio.run(investigate(Path(a.run_dir), a.thread, a.decision), loop_factory=loop)
    print(json.dumps(out, indent=2))
