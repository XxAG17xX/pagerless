"""Draw the README architecture diagram as two static SVGs (light and dark).

Usage: uv run docs/media/architecture.py
"""

from pathlib import Path

THEMES = {
    "light": {"surface": "#fcfcfb", "box": "#f2f1ed", "line": "#cfcec8", "text": "#0b0b0b", "text2": "#52514e",
              "accent": "#2a78d6", "accent_box": "#e7f0fb", "borrowed": "#f7f6f2"},
    "dark": {"surface": "#1a1a19", "box": "#242423", "line": "#4a4a46", "text": "#f0efec", "text2": "#c3c2b7",
             "accent": "#3987e5", "accent_box": "#18263a", "borrowed": "#1f1f1e"},
}
FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"
W, H = 980, 470


def box(t, x, y, w, h, title, sub="", fill=None, stroke=None, dashed=False, title_size=15):
    dash = ' stroke-dasharray="5 4"' if dashed else ""
    lines = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="9" fill="{fill or t["box"]}" '
             f'stroke="{stroke or t["line"]}" stroke-width="1.2"{dash}/>',
             f'<text x="{x + 14}" y="{y + 25}" font-size="{title_size}" font-weight="600" fill="{t["text"]}">{title}</text>']
    for i, s in enumerate(sub.split("\n") if sub else []):
        lines.append(f'<text x="{x + 14}" y="{y + 45 + i * 17}" font-size="12.5" fill="{t["text2"]}">{s}</text>')
    return "".join(lines)


def arrow(t, d, label="", lx=0, ly=0, dashed=False, anchor="start"):
    dash = ' stroke-dasharray="5 4"' if dashed else ""
    out = f'<path d="{d}" fill="none" stroke="{t["text2"]}" stroke-width="1.5" marker-end="url(#arrow)"{dash}/>'
    if label:
        out += f'<text x="{lx}" y="{ly}" font-size="12" fill="{t["text2"]}" text-anchor="{anchor}">{label}</text>'
    return out


def render(t):
    p = []
    # column 1: the system under test, the harness and the alerts
    p.append(box(t, 24, 64, 236, 78, "Fault harness", "faults/inject.py: injects faults,\nrecords the ground truth"))
    p.append(box(t, 24, 186, 236, 70, "OpenTelemetry Demo", "20 services in Docker", fill=t["borrowed"], dashed=True))
    p.append(box(t, 24, 300, 236, 78, "Prometheus, Jaeger, OpenSearch", "metrics, traces, logs,\nplus the alert rules", title_size=14))
    p.append(arrow(t, "M142,142 V180", "injects a fault", 152, 166))
    p.append(arrow(t, "M142,256 V294", "telemetry", 152, 280))
    # column 2: MCP servers
    p.append(f'<text x="300" y="138" font-size="12" font-weight="600" letter-spacing="0.06em" fill="{t["text2"]}">MCP SERVERS, READ-ONLY</text>')
    for i, (name, src) in enumerate([("metrics", "Prometheus"), ("traces", "Jaeger"), ("logs", "OpenSearch"),
                                     ("incident memory", "pgvector + full-text")]):
        y = 150 + i * 58
        p.append(f'<rect x="300" y="{y}" width="200" height="46" rx="8" fill="{t["box"]}" stroke="{t["line"]}" stroke-width="1.2"/>'
                 f'<text x="314" y="{y + 20}" font-size="14" font-weight="600" fill="{t["text"]}">{name}</text>'
                 f'<text x="314" y="{y + 37}" font-size="12" fill="{t["text2"]}">{src}</text>')
    # column 3: the agent
    p.append(box(t, 556, 168, 214, 150, "Agent (Claude API)",
                 "plain loop, or LangGraph\nwith Postgres checkpoints,\nso a crashed run resumes",
                 fill=t["accent_box"], stroke=t["accent"]))
    p.append(f'<path d="M506,243 H550" fill="none" stroke="{t["text2"]}" stroke-width="1.5" marker-end="url(#arrow)" marker-start="url(#arrow-back)"/>')
    p.append(f'<text x="528" y="234" font-size="12" fill="{t["text2"]}" text-anchor="middle">MCP</text>')
    p.append(arrow(t, "M260,360 H278 V420 H663 V324", "an alert fires: investigation starts", 300, 413))
    # column 4: outputs
    p.append(box(t, 810, 92, 150, 64, "Cited report", "root cause + evidence", title_size=14))
    p.append(box(t, 810, 196, 150, 64, "Human approves", "any fix, or not", title_size=14))
    p.append(box(t, 810, 300, 150, 78, "Score", "vs ground truth;\nCI fails below a floor", title_size=14))
    p.append(arrow(t, "M770,200 H790 V124 H804"))
    p.append(arrow(t, "M885,156 V190"))
    p.append(arrow(t, "M770,290 H790 V339 H804"))
    # the ground truth goes around the agent, never through it
    p.append(arrow(t, "M142,64 V40 H970 V339 H966", "ground truth, not visible to the agent", 560, 33, dashed=True, anchor="middle"))
    defs = (f'<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
            f'<path d="M0,0 L10,5 L0,10 z" fill="{t["text2"]}"/></marker>'
            f'<marker id="arrow-back" viewBox="0 0 10 10" refX="1" refY="5" markerWidth="7" markerHeight="7" orient="auto">'
            f'<path d="M10,0 L0,5 L10,10 z" fill="{t["text2"]}"/></marker></defs>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{FONT}" '
            f'role="img" aria-label="Pagerless architecture">{defs}'
            f'<rect width="{W}" height="{H}" rx="10" fill="{t["surface"]}"/>{"".join(p)}</svg>\n')


for name, theme in THEMES.items():
    Path(f"docs/media/architecture-{name}.svg").write_text(render(theme), encoding="utf-8")
print("wrote docs/media/architecture-light.svg and architecture-dark.svg")
