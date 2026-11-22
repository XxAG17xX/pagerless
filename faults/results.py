"""Build the results table from every runs/*/score.json (one row per incident) into docs/results.md
and docs/results.json (the summary the CI gate checks).

Usage: uv run faults/results.py
"""

import json
import statistics
from pathlib import Path

PRICES = {"claude-sonnet-5-5": (2.00, 10.00, 0.10), "claude-haiku-5-5": (0.10, 0.50, 0.01),
          "claude-opus-5-5": (4.00, 20.00, 0.20)}  # $ per 1M tokens: input, output, cache read

incidents = []  # every incident; nothing is dropped, re-runs count as new incidents
for score_file in sorted(Path("runs").glob("*/score.json")):
    score = json.loads(score_file.read_text())
    truth = json.loads((score_file.parent / "truth.json").read_text())
    traces = [json.loads(p.read_text()) for p in sorted(score_file.parent.glob("attempt_*/trace.json"))]
    incidents.append({"run": score_file.parent.name, "score": score, "truth": truth, "traces": traces,
                      "memory": score.get("memory", "off")})


def costs(traces: list) -> tuple[float, float]:
    """Actual cost, and what the same measured tokens would cost with no prompt caching."""
    cost = no_cache = 0.0
    for t in traces:
        p_in, p_out, p_cache = PRICES[t["model"]]
        u = t["usage"]
        cost += (u["input"] * p_in + u["output"] * p_out + u["cache_read"] * p_cache + u["cache_write"] * p_in * 1.25) / 1e6
        no_cache += ((u["input"] + u["cache_read"] + u["cache_write"]) * p_in + u["output"] * p_out) / 1e6
    return cost, no_cache


def summary(group: list) -> dict:
    attempts = [a for i in group for a in i["score"]["attempts"]]
    based = [i["truth"]["baseline"] for i in group if i["truth"].get("baseline")]  # first run predates the baseline
    cost, no_cache = costs([t for i in group for t in i["traces"]])
    return {
        "incidents": len(group), "fault_types": len({i["score"]["fault"] for i in group}),
        "attempts": len(attempts), "attempts_correct": sum(a["correct"] for a in attempts),
        "accuracy": round(sum(a["correct"] for a in attempts) / len(attempts), 4),
        "pass4": sum(i["score"]["pass_all"] for i in group),
        "baseline_incidents": len(based), "baseline_correct": sum(b["correct"] for b in based),
        "median_seconds": statistics.median(a["seconds"] for a in attempts),
        "median_tool_calls": statistics.median(a["tool_calls"] for a in attempts),
        "median_cost_usd": statistics.median(a["cost_usd"] for a in attempts),
        "total_cost_usd": round(cost, 2), "cost_without_caching_usd": round(no_cache, 2),
    }


rows = []
for i in sorted(incidents, key=lambda i: (i["memory"], i["score"]["fault"], i["run"])):
    s, t = i["score"], i["truth"]
    b = t.get("baseline")
    base = f"{b['root_cause_service'] or 'none'} ({'right' if b['correct'] else 'wrong'})" if b else "not run"
    right = sum(a["correct"] for a in s["attempts"])
    rows.append(f"| {s['fault']} | {t['root_cause_service']} | {i['memory']} | {right}/{len(s['attempts'])} | "
                f"{'yes' if s['pass_all'] else 'no'} | {base} | {t.get('seconds_to_alert')} s |")

modes = {m: summary([i for i in incidents if i["memory"] == m]) for m in ("off", "seen", "holdout")
         if any(i["memory"] == m for i in incidents)}
model = incidents[0]["traces"][0]["model"]
lines = [
    "# Results", "",
    f"Agent: {model}, plain tool-use loop over read-only MCP servers (metrics, traces, logs; plus incident "
    "memory when memory is on). Each fault was injected into the borrowed OpenTelemetry Demo; after an alert "
    "fired, the agent investigated 4 times while the fault was live. The rules baseline answered once at the "
    "same moment. Memory: off = no memory; seen = every past incident searchable; holdout = past incidents "
    "of the same fault type hidden.", "",
    "| Fault | True cause | Memory | Agent correct | pass^4 | Rules baseline | Alert after |",
    "|---|---|---|---|---|---|---|", *rows, "",
]
for m, r in modes.items():
    lines += [
        f"**Memory {m}:** agent {r['attempts_correct']}/{r['attempts']} attempts correct ({r['accuracy']:.0%}), "
        f"pass^4 on {r['pass4']}/{r['incidents']} incidents across {r['fault_types']} fault types; "
        f"rules baseline {r['baseline_correct']}/{r['baseline_incidents']}; median {r['median_seconds']:.0f} s, "
        f"{r['median_tool_calls']:.0f} tool calls, ${r['median_cost_usd']:.3f} per investigation; total "
        f"${r['total_cost_usd']:.2f}, or ${r['cost_without_caching_usd']:.2f} for the same tokens without prompt "
        f"caching ({1 - r['total_cost_usd'] / r['cost_without_caching_usd']:.0%} saved, computed from measured "
        "token counts).", ""]

Path("docs").mkdir(exist_ok=True)
Path("docs/results.md").write_text("\n".join(lines))
Path("docs/results.json").write_text(json.dumps({"model": model, "modes": modes}, indent=2) + "\n")
print("\n".join(lines))
