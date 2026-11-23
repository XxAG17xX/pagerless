"""Draw the README results chart from docs/results.json, as two static SVGs (light and dark).

Usage: uv run docs/media/results_chart.py
Static images on GitHub cannot have hover, so every bar carries its value and its n; the full
numbers stay in docs/results.md. Colours: the dataviz reference palette, one series (slot 1).
"""

import json
from pathlib import Path

modes = json.loads(Path("docs/results.json").read_text())["modes"]
std = modes["standard"]

# (group, label, correct, total)
rows = [
    ("Diagnosis", "Agent", std["attempts_correct"], std["attempts"]),
    ("Diagnosis", "Agent + incident memory (fault type hidden)", modes["memory holdout"]["attempts_correct"], modes["memory holdout"]["attempts"]),
    ("Diagnosis", "Agent in code mode", modes["code mode"]["attempts_correct"], modes["code mode"]["attempts"]),
    ("Diagnosis", "Rules-based runbook, no AI", std["baseline_correct"], std["baseline_incidents"]),
    ("Under prompt injection", "No defence", modes["injection attack, no defence"]["attempts_correct"], modes["injection attack, no defence"]["attempts"]),
    ("Under prompt injection", "With defence", modes["injection attack, with defence"]["attempts_correct"], modes["injection attack, with defence"]["attempts"]),
]

THEMES = {
    "light": {"surface": "#fcfcfb", "text": "#0b0b0b", "text2": "#52514e", "grid": "#e4e3de", "bar": "#2a78d6"},
    "dark": {"surface": "#1a1a19", "text": "#f0efec", "text2": "#c3c2b7", "grid": "#383835", "bar": "#3987e5"},
}
W, LEFT, RIGHT, BAR, ROW, GROUP_GAP, TOP = 920, 330, 112, 22, 40, 34, 78
FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"


def bar(x: float, y: float, w: float, h: float, r: float = 4) -> str:
    """Square at the baseline (left), 4px rounded data-end (right)."""
    if w < r:
        return f'<rect x="{x}" y="{y}" width="{w:.1f}" height="{h}"/>'
    return (f'<path d="M{x},{y} H{x + w - r:.1f} Q{x + w:.1f},{y} {x + w:.1f},{y + r} V{y + h - r} '
            f'Q{x + w:.1f},{y + h} {x + w - r:.1f},{y + h} H{x} Z"/>')


def render(t: dict) -> str:
    plot = W - LEFT - RIGHT
    out, y, group = [], TOP, None
    for g, label, ok, n in rows:
        if g != group:
            y += GROUP_GAP if group else 0
            out.append(f'<text x="24" y="{y + 4}" font-size="13" font-weight="600" fill="{t["text2"]}" '
                       f'letter-spacing="0.06em">{g.upper()}</text>')
            y += 22
            group = g
        share = ok / n
        out.append(f'<text x="{LEFT - 16}" y="{y + BAR / 2 + 5}" text-anchor="end" font-size="15" fill="{t["text"]}">{label}</text>')
        out.append(f'<g fill="{t["bar"]}">{bar(LEFT, y, plot * share, BAR)}</g>')
        out.append(f'<text x="{LEFT + plot * share + 10:.1f}" y="{y + BAR / 2 + 5}" font-size="15" fill="{t["text"]}">'
                   f'<tspan font-weight="600">{share:.0%}</tspan><tspan fill="{t["text2"]}"> {ok}/{n}</tspan></text>')
        y += ROW
    height = y + 30
    grid = "".join(
        f'<line x1="{LEFT + plot * p:.1f}" x2="{LEFT + plot * p:.1f}" y1="{TOP - 6}" y2="{y - 10}" stroke="{t["grid"]}" stroke-width="1"/>'
        f'<text x="{LEFT + plot * p:.1f}" y="{y + 8}" text-anchor="middle" font-size="12" fill="{t["text2"]}">{p:.0%}</text>'
        for p in (0, 0.25, 0.5, 0.75, 1))
    title = (f'<text x="24" y="34" font-size="19" font-weight="600" fill="{t["text"]}">Correct root cause, share of attempts</text>'
             f'<text x="24" y="56" font-size="13" fill="{t["text2"]}">Claude Sonnet 5.5, 8 fault types injected into the OpenTelemetry Demo, '
             f'4 attempts per incident (rules baseline: one answer per incident)</text>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{height}" viewBox="0 0 {W} {height}" '
            f'font-family="{FONT}" role="img" aria-label="Bar chart of correct root cause per condition">'
            f'<rect width="{W}" height="{height}" rx="10" fill="{t["surface"]}"/>{title}{grid}{"".join(out)}</svg>\n')


for name, theme in THEMES.items():
    Path(f"docs/media/results-{name}.svg").write_text(render(theme), encoding="utf-8")
print("wrote docs/media/results-light.svg and results-dark.svg")
