"""Build the results table from every runs/*/score.json (one row per incident) into docs/results.md.

Usage: uv run faults/results.py
"""

import json
import statistics
from pathlib import Path

PRICES = {"claude-sonnet-5-5": (2.00, 10.00, 0.10), "claude-haiku-5-5": (0.10, 0.50, 0.01),
          "claude-opus-5-5": (4.00, 20.00, 0.20)}  # $ per 1M tokens: input, output, cache read

latest = {}  # every incident, keyed by run folder; nothing is dropped, re-runs count as new incidents
for score_file in sorted(Path("runs").glob("*/score.json")):
    score = json.loads(score_file.read_text())
    truth = json.loads((score_file.parent / "truth.json").read_text())
    latest[score_file.parent.name] = (score_file.parent, score, truth)

rows, attempts, traces = [], [], []
for _, (run_dir, score, truth) in sorted(latest.items(), key=lambda kv: (kv[1][1]["fault"], kv[0])):
    fault = score["fault"]
    right = sum(a["correct"] for a in score["attempts"])
    attempts += score["attempts"]
    traces += [json.loads(p.read_text()) for p in sorted(run_dir.glob("attempt_*/trace.json"))]
    base = truth.get("baseline") or {}
    rows.append(f"| {fault} | {truth['root_cause_service']} | {right}/{len(score['attempts'])} | "
                f"{'yes' if score['pass_all'] else 'no'} | "
                f"{(base.get('root_cause_service') or 'none') + (' (right)' if base.get('correct') else ' (wrong)') if base else 'not run'} | "
                f"{truth.get('seconds_to_alert')} s |")

n_faults, n_att = len(latest), len(attempts)  # n_faults counts incidents
n_types = len({s["fault"] for _, s, _ in latest.values()})
agent_right = sum(a["correct"] for a in attempts)
pass4 = sum(s["pass_all"] for _, s, _ in latest.values())
based = [t["baseline"] for _, _, t in latest.values() if t.get("baseline")]  # first run predates the baseline
base_right = sum(b["correct"] for b in based)

# Prompt caching: what the same measured token counts would cost with every cached token billed as fresh input.
cost = no_cache = 0.0
for t in traces:
    p_in, p_out, p_cache = PRICES[t["model"]]
    u = t["usage"]
    cost += (u["input"] * p_in + u["output"] * p_out + u["cache_read"] * p_cache + u["cache_write"] * p_in * 1.25) / 1e6
    no_cache += ((u["input"] + u["cache_read"] + u["cache_write"]) * p_in + u["output"] * p_out) / 1e6

lines = [
    "# Results", "",
    f"Agent: {traces[0]['model']}, plain tool-use loop over 3 read-only MCP servers (metrics, traces, logs).",
    "Each fault was injected into the borrowed OpenTelemetry Demo; after an alert fired, the agent "
    "investigated 4 times while the fault was live. The rules baseline answered once at the same moment.", "",
    "| Fault | True cause | Agent correct | pass^4 | Rules baseline | Alert after |",
    "|---|---|---|---|---|---|", *rows, "",
    f"- **Agent:** {agent_right}/{n_att} attempts correct ({agent_right / n_att:.0%}); "
    f"pass^4 on {pass4}/{n_faults} incidents across {n_types} fault types.",
    f"- **Rules baseline:** {base_right}/{len(based)} incidents correct ({base_right / len(based):.0%}).",
    f"- **Per investigation (median):** {statistics.median(a['seconds'] for a in attempts):.0f} s, "
    f"{statistics.median(a['tool_calls'] for a in attempts):.0f} tool calls, "
    f"${statistics.median(a['cost_usd'] for a in attempts):.3f}.",
    f"- **Total API cost of these {n_att} investigations:** ${cost:.2f}. Billing the same tokens without "
    f"prompt caching would have cost ${no_cache:.2f}, so caching cut cost by {1 - cost / no_cache:.0%} "
    "(computed from measured token counts, not a separate run).",
]
Path("docs").mkdir(exist_ok=True)
Path("docs/results.md").write_text("\n".join(lines) + "\n")
print("\n".join(lines))
