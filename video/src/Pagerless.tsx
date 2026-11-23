// A 51-second replay of one real Pagerless incident (runs/20261123T204228Z_payment-down).
// Every name, number and finding comes from that run's truth/trace/report files and docs/results.json.
// One service map stays on screen and carries the story: payment stops, errors spread upstream,
// the agent's attention moves across it, and the cause it names lights up.
import React from "react";
import {AbsoluteFill, Easing, interpolate, interpolateColors, useCurrentFrame, useVideoConfig} from "remotion";
import {loadFont} from "@remotion/google-fonts/MartianMono";
import truth from "../public/run/truth.json";
import trace from "../public/run/trace.json";
import results from "../public/run/results.json";

// One typeface throughout, an incident-log voice.
const {fontFamily: FONT} = loadFont("normal", {weights: ["300", "400", "500", "600"], subsets: ["latin"]});
const HEAD = FONT, SANS = FONT, MONO = FONT, HW = 400, HLS = "-0.03em";

export const SECONDS = 51;

const C = {
  bg: "#0a0b0d", panel: "#111317", panelHi: "#16191e", line: "#22262d", line2: "#313742",
  text: "#f3f4f6", text2: "#aab0bb", muted: "#6c7380", accent: "#5b9cff", red: "#ff5f5f",
  green: "#3ecf8e", amber: "#f5a524", purple: "#b78cff", teal: "#2dd4bf",
};
const SRC: Record<string, [string, string]> = {prometheus: ["METRICS", C.accent], jaeger: ["TRACES", C.purple], logs: ["LOGS", C.teal]};

// ---- timing (seconds) ----
const T = {brk: 4.2, kill: 7.4, alert: 10.2, pending: 11.6, firing: 12.8, inv: 15.2, report: 31, score: 39.2, end: 47.4};
const CALLS = [16.2, 17.9, 19.4, 20.9, 22.4, 25.2, 26.7, 28.2]; // the key finding (index 4) gets the longest dwell
const FAIL: Record<string, number> = {payment: T.kill, checkout: T.kill + 0.55, frontend: T.kill + 1.0, "frontend-proxy": T.kill + 1.4};

// ---- easing helpers ----
const cl = {extrapolateLeft: "clamp", extrapolateRight: "clamp"} as const;
const OUT = Easing.bezier(0.16, 1, 0.3, 1); // entrances
const INOUT = Easing.bezier(0.65, 0, 0.35, 1); // things already on screen that move
const tw = (s: number, at: number, d: number, e = OUT) => interpolate(s, [at, at + d], [0, 1], {...cl, easing: e});
const lerp = (p: number, a: number, b: number) => a + (b - a) * p;
const life = (s: number, a: number, b: number, fi = 0.5, fo = 0.4) => Math.min(tw(s, a, fi), 1 - tw(s, b - fo, fo, INOUT));

const Rise: React.FC<{s: number; at: number; until?: number; dy?: number; d?: number; style?: React.CSSProperties; children: React.ReactNode}> =
  ({s, at, until, dy = 16, d = 0.7, style, children}) => {
    const p = tw(s, at, d);
    const out = until ? tw(s, until - 0.4, 0.4, INOUT) : 0;
    return <div style={{...style, opacity: p * (1 - out), transform: `translateY(${(1 - p) * dy - out * 10}px)`}}>{children}</div>;
  };

const Tag: React.FC<{label: string; color: string}> = ({label, color}) => (
  <span style={{fontSize: 14, fontWeight: 600, letterSpacing: "0.08em", color, padding: "4px 9px", borderRadius: 6,
    background: color + "1f", fontFamily: SANS}}>{label}</span>
);

const Icon: React.FC<{kind: "check" | "cross" | "lock"; color: string; size?: number}> = ({kind, color, size = 40}) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={2.4} strokeLinecap="round" strokeLinejoin="round">
    {kind === "check" && <path d="M5 12.5l4.5 4.5L19 7.5" />}
    {kind === "cross" && <path d="M6.5 6.5l11 11M17.5 6.5l-11 11" />}
    {kind === "lock" && <><rect x="5" y="11" width="14" height="9" rx="2" /><path d="M8 11V8a4 4 0 018 0v3" /></>}
  </svg>
);

// ---- the service map ----
const NW = 224, NH = 54;
const NODES: Record<string, [number, number]> = {
  "frontend-proxy": [105, 280], frontend: [405, 280], checkout: [705, 280],
  cart: [1005, 50], "product-catalog": [1005, 142], currency: [1005, 234], payment: [1005, 326], shipping: [1005, 418], email: [1005, 510],
};
const EDGES: [string, string][] = [["frontend-proxy", "frontend"], ["frontend", "checkout"],
  ...["cart", "product-catalog", "currency", "payment", "shipping", "email"].map((n) => ["checkout", n] as [string, string])];
// which services each of the 8 tool calls looked at
const LOOK = [["checkout"], ["checkout", "frontend", "frontend-proxy"], ["checkout"], ["checkout"], ["checkout", "payment"], [], ["payment"], ["payment"]];

const edgePath = (a: string, b: string) => {
  const [x1, y1] = NODES[a], [x2, y2] = NODES[b];
  const sx = x1 + NW / 2, ex = x2 - NW / 2, mx = (sx + ex) / 2;
  return `M${sx},${y1} C${mx},${y1} ${mx},${y2} ${ex},${y2}`;
};
const callLife = (s: number, i: number) => life(s, CALLS[i], CALLS[i + 1] ?? T.report, 0.3, 0.3);

const ServiceMap: React.FC<{s: number}> = ({s}) => {
  const err = (n: string) => (n in FAIL ? tw(s, FAIL[n], 0.45) : 0);
  const look = (n: string) => Math.max(0, ...LOOK.map((ns, i) => (ns.includes(n) ? callLife(s, i) : 0)));
  const keyEdge = Math.max(callLife(s, 4), life(s, T.report + 0.3, T.score, 0.6, 0.4));
  const cause = life(s, T.report + 0.3, T.score, 0.6, 0.4);
  // carry: the whole map moves as one object
  const side = tw(s, T.alert - 0.2, 1.2, INOUT);
  const intro = tw(s, 3.6, 1.1, INOUT);
  const cx = lerp(side, 960, 505), cy = lerp(side, 610, 620), sc = lerp(side, 1, 0.77) * lerp(intro, 0.94, 1);
  const opacity = intro * (1 - tw(s, T.score - 0.3, 0.6, INOUT));
  return (
    <svg width={1130} height={560} viewBox="0 0 1130 560" style={{position: "absolute", left: cx - 565, top: cy - 280,
      transform: `scale(${sc})`, opacity, overflow: "visible", fontFamily: SANS}}>
      <defs><filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="6" /></filter></defs>
      {EDGES.map(([a, b]) => {
        const d = edgePath(a, b);
        const dead = b === "payment" ? err("payment") : 0;
        const flow = interpolateColors(err(b), [0, 1], ["#8a93a3", C.red]);
        return (
          <g key={b}>
            <path d={d} fill="none" stroke={interpolateColors(dead, [0, 1], [C.line2, C.red + "99"])} strokeWidth={2}
              strokeDasharray={dead > 0.5 ? "6 8" : undefined} />
            <path d={d} fill="none" stroke={flow} strokeWidth={3} strokeLinecap="round" strokeDasharray="2 16"
              strokeDashoffset={-s * 60} opacity={0.75 * (1 - dead)} />
            {b === "payment" && <>
              <path d={d} fill="none" stroke={C.red} strokeWidth={8} opacity={keyEdge * 0.5} filter="url(#glow)" />
              <path d={d} fill="none" stroke={C.red} strokeWidth={3} opacity={keyEdge} />
            </>}
          </g>
        );
      })}
      {Object.entries(NODES).map(([n, [x, y]]) => {
        const e = err(n), down = n === "payment" ? e : 0, l = look(n);
        const ring = n in FAIL ? tw(s, FAIL[n], 1.0, Easing.out(Easing.quad)) : 0;
        const status = n === "payment" ? "stopped" : "errors";
        return (
          <g key={n}>
            {ring > 0 && ring < 1 && <rect x={x - NW / 2 - ring * 22} y={y - NH / 2 - ring * 22} width={NW + ring * 44} height={NH + ring * 44}
              rx={14 + ring * 16} fill="none" stroke={C.red} strokeWidth={2} opacity={(1 - ring) * 0.8} />}
            <rect x={x - NW / 2 - 7} y={y - NH / 2 - 7} width={NW + 14} height={NH + 14} rx={18} fill={C.accent} opacity={l * 0.1} />
            <rect x={x - NW / 2 - 7} y={y - NH / 2 - 7} width={NW + 14} height={NH + 14} rx={18} fill="none" stroke={C.accent} strokeWidth={2.5} opacity={l} />
            {n === "payment" && <rect x={x - NW / 2 - 9} y={y - NH / 2 - 9} width={NW + 18} height={NH + 18} rx={20} fill="none"
              stroke={C.red} strokeWidth={3} opacity={cause * (0.75 + 0.25 * Math.sin(s * 5))} />}
            <rect x={x - NW / 2} y={y - NH / 2} width={NW} height={NH} rx={12}
              fill={interpolateColors(down, [0, 1], [C.panelHi, "#1c1012"])} stroke={interpolateColors(e, [0, 1], [C.line2, C.red])} strokeWidth={1.5} />
            <circle cx={x - NW / 2 + 22} cy={y} r={6} fill={interpolateColors(e, [0, 1], [C.green, C.red])} />
            <text x={x - NW / 2 + 36} y={y + 6} fontSize={16} fontWeight={400} fill={interpolateColors(down, [0, 1], [C.text, C.muted])}>{n}</text>
            <text x={x} y={y + NH / 2 + 21} fontSize={13} fontWeight={500} textAnchor="middle" fill={C.red} opacity={e}
              letterSpacing="0.06em">{e > 0 ? status.toUpperCase() : ""}</text>
          </g>
        );
      })}
    </svg>
  );
};

// ---- chrome: step captions and the progress rail ----
const ALERT_AT = new Date(Date.parse(truth.injected_at) + truth.seconds_to_alert * 1000).toISOString().slice(11, 19);
const STEPS: [number, number, string, string, string][] = [
  [T.brk, T.alert - 0.2, `${truth.injected_at.slice(11, 19)} UTC`, "payment stops", "Fault injected into the OpenTelemetry Demo"],
  [T.alert, T.inv - 0.2, `${ALERT_AT} UTC`, "CheckoutFailing fires", "Prometheus pages the agent"],
  [T.inv, T.report - 0.2, "Investigation", `${trace.tool_calls} tool calls, ${trace.seconds} seconds`, "Read-only access to metrics, traces and logs"],
  [T.report, T.score - 0.2, "Report", "Every claim cites its evidence", "The fix waits for approval"],
  [T.score, T.end - 0.2, "Evaluation", "Checked against the injected fault", "Then the same check across every run"],
];
const RAIL = ["Fault", "Alert", "Investigate", "Report", "Score"];

const Chrome: React.FC<{s: number}> = ({s}) => {
  const prog = interpolate(s, STEPS.map((st) => st[0]), [0, 0.25, 0.5, 0.75, 1], cl);
  const railOn = life(s, T.brk, T.end, 0.8, 0.5);
  return (
    <>
      {STEPS.map(([a, b, eyebrow, title, sub]) => (
        <div key={title} style={{position: "absolute", left: 120, top: 92}}>
          <Rise s={s} at={a + 0.1} until={b} dy={18}>
            <div style={{fontFamily: MONO, fontSize: 18, color: C.accent, letterSpacing: "0.1em"}}>{eyebrow}</div>
            <div style={{fontFamily: HEAD, fontSize: 54, fontWeight: HW, letterSpacing: HLS, marginTop: 10}}>{title}</div>
          </Rise>
          <Rise s={s} at={a + 0.25} until={b} dy={10}>
            <div style={{fontSize: 22, color: C.text2, marginTop: 12}}>{sub}</div>
          </Rise>
        </div>
      ))}
      <div style={{position: "absolute", left: 560, top: 1002, width: 800, opacity: railOn}}>
        <div style={{position: "absolute", top: 5, left: 0, width: 800, height: 2, background: C.line}} />
        <div style={{position: "absolute", top: 5, left: 0, width: 800 * prog, height: 2, background: C.accent}} />
        {RAIL.map((r, i) => {
          const on = prog >= i / 4 - 0.001;
          const current = on && (i === 4 || prog < (i + 1) / 4);
          return (
            <div key={r} style={{position: "absolute", left: (800 * i) / 4, transform: "translateX(-50%)", textAlign: "center"}}>
              <div style={{width: 12, height: 12, borderRadius: 6, margin: "0 auto", background: on ? C.accent : C.bg,
                border: `2px solid ${on ? C.accent : C.line2}`}} />
              <div style={{fontSize: 17, marginTop: 10, color: current ? C.text : C.muted, fontWeight: current ? 600 : 400}}>{r}</div>
            </div>
          );
        })}
      </div>
    </>
  );
};

// ---- scenes ----
const Title: React.FC<{s: number}> = ({s}) => {
  const p = tw(s, 0.25, 0.9);
  const out = tw(s, 3.3, 0.5, INOUT);
  return (
    <div style={{position: "absolute", left: 160, top: 360, opacity: 1 - out, transform: `translateY(${-out * 16}px)`}}>
      <div style={{overflow: "hidden", paddingBottom: 12}}>
        <div style={{fontFamily: HEAD, fontSize: 150, fontWeight: HW, letterSpacing: HLS, lineHeight: 1, transform: `translateY(${(1 - p) * 105}%)`}}>Pagerless</div>
      </div>
      <Rise s={s} at={0.6} dy={12}><div style={{fontSize: 32, color: C.text2, marginTop: 24}}>An on-call agent for microservices.</div></Rise>
      <div style={{fontSize: 20, color: C.muted, marginTop: 22, opacity: tw(s, 1.2, 0.8)}}>Incident {truth.injected_at.slice(0, 10)} · {truth.fault}</div>
    </div>
  );
};

const Break: React.FC<{s: number}> = ({s}) => {
  const cmd = "docker stop payment";
  const typed = cmd.slice(0, Math.round(interpolate(s, [5.3, 6.5], [0, cmd.length], cl)));
  const caret = s < 7.0 && Math.floor(s * 2.2) % 2 === 0;
  const on = life(s, 4.8, T.alert, 0.6, 0.4);
  return (
    <div style={{position: "absolute", left: 1240, top: 96, width: 560, opacity: on, transform: `translateY(${(1 - tw(s, 4.8, 0.7)) * 14}px)`}}>
      <div style={{background: C.panel, border: `1px solid ${C.line}`, borderRadius: 14, padding: "18px 24px", fontFamily: MONO}}>
        <div style={{fontSize: 16, color: C.muted}}>faults/inject.py · {truth.injected_at.slice(11, 19)} UTC</div>
        <div style={{fontSize: 28, marginTop: 10}}><span style={{color: C.accent}}>$ </span>{typed}<span style={{opacity: caret ? 1 : 0, color: C.accent}}>▍</span></div>
      </div>
      <div style={{display: "flex", alignItems: "center", gap: 14, marginTop: 16, opacity: tw(s, 8.9, 0.6), fontSize: 22, color: C.text2}}>
        <Icon kind="lock" color={C.muted} size={26} /> ground truth recorded:
        <b style={{color: C.text}}>{truth.root_cause_service}</b>
      </div>
    </div>
  );
};

const Alert: React.FC<{s: number}> = ({s}) => {
  const on = life(s, T.alert + 1.0, T.inv, 0.7, 0.4);
  return (
    <div style={{position: "absolute", left: 1010, top: 330, width: 810, opacity: on, transform: `translateY(${(1 - tw(s, T.alert + 1.0, 0.8)) * 20}px)`}}>
      <div style={{background: C.panel, border: `1px solid ${C.line}`, borderRadius: 18, padding: "26px 30px"}}>
        <div style={{fontSize: 18, color: C.muted}}><span style={{fontFamily: MONO}}>prometheus/alerts.yml</span></div>
        {truth.alerts.map((a, i) => {
          const off = i * 0.25; // the second alert trails the first a little
          const color = interpolateColors(s, [T.pending + off - 0.15, T.pending + off + 0.15, T.firing + off - 0.15, T.firing + off + 0.15],
            [C.muted, C.amber, C.amber, C.red]);
          const label = s < T.pending + off ? "inactive" : s < T.firing + off ? "pending" : "firing";
          const pulse = tw(s, T.firing + off, 0.9, Easing.out(Easing.quad));
          return (
            <div key={a} style={{display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 22,
              padding: "18px 22px", background: C.panelHi, borderRadius: 12, borderLeft: `4px solid ${color}`}}>
              <span style={{fontSize: 30, fontWeight: 500}}>{a}</span>
              <span style={{position: "relative", fontSize: 17, fontWeight: 600, letterSpacing: "0.08em", color, padding: "6px 14px",
                borderRadius: 999, border: `1.5px solid ${color}`}}>
                {label.toUpperCase()}
                {pulse > 0 && pulse < 1 && <span style={{position: "absolute", inset: -pulse * 12, borderRadius: 999, border: `2px solid ${C.red}`, opacity: 1 - pulse}} />}
              </span>
            </div>
          );
        })}
      </div>
      <Rise s={s} at={T.firing + 0.5} dy={12} style={{marginTop: 34, display: "flex", alignItems: "baseline", gap: 18}}>
        <span style={{fontFamily: MONO, fontSize: 64, fontWeight: 500}}>+{Math.floor(truth.seconds_to_alert / 60)}:{String(truth.seconds_to_alert % 60).padStart(2, "0")}</span>
        <span style={{fontSize: 24, color: C.text2}}>after the fault</span>
      </Rise>
      <Rise s={s} at={T.firing + 1.3} dy={8} style={{marginTop: 14, fontSize: 24, color: C.accent}}>Agent paged →</Rise>
    </div>
  );
};

const READINGS = [
  "CheckoutFailing and ServiceErrors firing",
  "Errors in checkout and frontends, not payment",
  "5 failing checkout traces",
  "No error logs from checkout",
  "checkout → payment: 'produced zero addresses'",
  "17 services known to Jaeger",
  "payment request rate: 0",
  "Last payment log 20:42:00, then nothing",
];
const PITCH = 104, VISIBLE = 5;

const Investigate: React.FC<{s: number}> = ({s}) => {
  const on = life(s, T.inv + 0.2, T.report, 0.7, 0.4);
  const done = CALLS.filter((c) => s >= c).length;
  const scroll = CALLS.reduce((acc, c, i) => acc + (i >= VISIBLE ? tw(s, c, 0.55, INOUT) : 0), 0);
  return (
    <div style={{position: "absolute", left: 1010, top: 300, width: 810, opacity: on, transform: `translateY(${(1 - tw(s, T.inv + 0.2, 0.8)) * 20}px)`}}>
      <div style={{display: "flex", justifyContent: "space-between", alignItems: "baseline"}}>
        <span style={{fontSize: 22, fontWeight: 600}}>Agent <span style={{fontFamily: MONO, fontSize: 18, color: C.muted, fontWeight: 400}}>{trace.model}</span></span>
        <span style={{fontFamily: MONO, fontSize: 18, color: C.text2}}>tool call {Math.max(done, 1)} of {CALLS.length}</span>
      </div>
      <div style={{position: "relative", height: PITCH * VISIBLE, marginTop: 20, overflow: "hidden",
        maskImage: "linear-gradient(to bottom, transparent 0, black 24px)"}}>
        {trace.steps.map((st, i) => {
          const [tag, color] = SRC[st.tool.split("_")[0]];
          const p = tw(s, CALLS[i], 0.55);
          const active = callLife(s, i);
          const key = i === 4;
          return (
            <div key={i} style={{position: "absolute", left: 0, right: 0, top: (i - scroll) * PITCH + 8, height: PITCH - 14,
              opacity: p * (1 - tw(s, CALLS[i + VISIBLE] ?? 1e9, 0.45)), transform: `translateY(${(1 - p) * 16}px)`,
              background: C.panel, borderRadius: 14, padding: "13px 20px", boxSizing: "border-box",
              border: `1.5px solid ${interpolateColors(active, [0, 1], [C.line, key ? C.red : C.accent])}`}}>
              <div style={{display: "flex", alignItems: "center", gap: 14}}>
                <Tag label={tag} color={color} />
                <span style={{fontFamily: MONO, fontSize: 15, color: C.muted}}>{st.tool}</span>
              </div>
              <div style={{fontSize: 20, marginTop: 10, color: key ? C.red : interpolateColors(active, [0, 1], [C.text2, C.text]),
                whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis"}}>{READINGS[i]}</div>
            </div>
          );
        })}
      </div>
      <div style={{marginTop: 22, fontFamily: MONO, fontSize: 22, color: C.text2, opacity: tw(s, CALLS[7] + 1.0, 0.6)}}>
        {trace.tool_calls} tool calls · {trace.seconds} s · ${trace.cost_usd.toFixed(3)}
      </div>
    </div>
  );
};

const EVIDENCE: [string, string][] = [
  ["jaeger", "checkout → payment Charge fails: 'name resolver error: produced zero addresses'"],
  ["prometheus", "payment's request rate is 0"],
  ["logs", "payment's last log is at 20:42:00, then nothing"],
];

const Report: React.FC<{s: number}> = ({s}) => {
  const a = T.report + 0.3;
  const on = life(s, a, T.score, 0.7, 0.4);
  const conf = tw(s, a + 0.6, 1.0) * 0.85;
  const blink = 0.45 + 0.55 * Math.abs(Math.sin((s - a) * 2.6));
  return (
    <div style={{position: "absolute", left: 1010, top: 280, width: 810, opacity: on, transform: `translateY(${(1 - tw(s, a, 0.8)) * 20}px)`,
      background: C.panel, border: `1px solid ${C.line}`, borderRadius: 18, padding: "28px 32px", boxSizing: "border-box"}}>
      <div style={{fontSize: 15, fontWeight: 600, letterSpacing: "0.12em", color: C.muted}}>ROOT CAUSE</div>
      <div style={{fontFamily: HEAD, fontSize: 96, fontWeight: HW, letterSpacing: HLS, lineHeight: 1.05, marginTop: 4}}>payment</div>
      <div style={{display: "flex", alignItems: "center", gap: 16, marginTop: 14}}>
        <div style={{width: 240, height: 8, borderRadius: 4, background: C.line}}>
          <div style={{width: 240 * conf, height: 8, borderRadius: 4, background: C.accent}} />
        </div>
        <span style={{fontFamily: MONO, fontSize: 19, color: C.text2}}>confidence {conf.toFixed(2)}</span>
      </div>
      <div style={{height: 1, background: C.line, margin: "24px 0 6px"}} />
      {EVIDENCE.map(([src, text]) => (
        <div key={text} style={{display: "flex", gap: 16, alignItems: "flex-start", marginTop: 14}}>
          <div style={{width: 96, flexShrink: 0, paddingTop: 2}}><Tag label={SRC[src][0]} color={SRC[src][1]} /></div>
          <span style={{fontSize: 19, lineHeight: 1.45}}>{text}</span>
        </div>
      ))}
      <div style={{height: 1, background: C.line, margin: "24px 0 18px"}} />
      <div style={{display: "flex", alignItems: "center", gap: 14}}>
        <span style={{fontSize: 18, color: C.muted}}>Suggested fix</span>
        <span style={{fontFamily: MONO, fontSize: 21, background: C.panelHi, border: `1px solid ${C.line2}`, borderRadius: 8, padding: "6px 12px"}}>docker compose up -d payment</span>
      </div>
      <div style={{display: "flex", alignItems: "center", gap: 12, marginTop: 20}}>
        <span style={{fontSize: 20, fontWeight: 600, padding: "10px 22px", borderRadius: 10, background: C.accent, color: "#06101f"}}>Approve</span>
        <span style={{fontSize: 20, fontWeight: 600, padding: "9px 22px", borderRadius: 10, border: `1.5px solid ${C.line2}`, color: C.text2}}>Reject</span>
        <span style={{display: "flex", alignItems: "center", gap: 10, marginLeft: 16, fontSize: 19, color: C.text2}}>
          <span style={{width: 9, height: 9, borderRadius: 5, background: C.amber, opacity: blink}} />awaiting approval
        </span>
      </div>
    </div>
  );
};

const Score: React.FC<{s: number}> = ({s}) => {
  const a = T.score + 0.2, swap = 42.7;
  const cards: [string, string, "lock" | "check" | "cross", string, number][] = [
    ["Ground truth", truth.root_cause_service, "lock", C.muted, a],
    ["Pagerless", truth.root_cause_service, "check", C.green, a + 0.5],
    ["Rules-based runbook", truth.baseline.root_cause_service, "cross", C.red, a + 0.85],
  ];
  const m = results.modes;
  const rows: [string | null, string, number, number, boolean][] = [
    ["Diagnosis", "Agent", m.standard.attempts_correct, m.standard.attempts, true],
    [null, "Agent + incident memory (fault type hidden)", m["memory holdout"].attempts_correct, m["memory holdout"].attempts, true],
    [null, "Agent in code mode", m["code mode"].attempts_correct, m["code mode"].attempts, true],
    [null, "Rules-based runbook, no AI", m.standard.baseline_correct, m.standard.baseline_incidents, false],
    ["Under prompt injection", "No defence", m["injection attack, no defence"].attempts_correct, m["injection attack, no defence"].attempts, false],
    [null, "With defence", m["injection attack, with defence"].attempts_correct, m["injection attack, with defence"].attempts, true],
  ];
  const DELAY = [0, 0.12, 0.22, 0.3, 0.55, 0.63]; // shrinking gaps read as a wave
  const cardsOut = tw(s, swap, 0.4, INOUT);
  const chartOn = life(s, swap + 0.3, T.end, 0.7, 0.4);
  let y = 0;
  return (
    <>
      <div style={{position: "absolute", left: 234, top: 450, display: "flex", gap: 36, opacity: 1 - cardsOut, transform: `translateY(${-cardsOut * 14}px)`}}>
        {cards.map(([label, value, icon, color, at], i) => {
          const p = tw(s, at, 0.7);
          const reveal = i === 0 ? tw(s, at + 0.5, 0.8) : 1;
          const pop = tw(s, at + 0.45, 0.5, Easing.out(Easing.back(2)));
          return (
            <div key={label} style={{width: 460, background: C.panel, borderRadius: 18, padding: "28px 32px", boxSizing: "border-box",
              border: `1.5px solid ${i === 0 ? C.line : color + "66"}`, opacity: p, transform: `translateY(${(1 - p) * (i === 0 ? 22 : 12)}px)`}}>
              <div style={{fontSize: 17, color: C.muted}}>{label}</div>
              <div style={{display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 12}}>
                <span style={{fontFamily: HEAD, fontSize: 52, fontWeight: HW, letterSpacing: HLS, filter: `blur(${(1 - reveal) * 14}px)`}}>{value}</span>
                <span style={{transform: `scale(${i === 0 ? 1 : pop})`, opacity: i === 0 ? 1 - reveal * 0.4 : pop}}><Icon kind={icon} color={color} size={48} /></span>
              </div>
            </div>
          );
        })}
      </div>
      <div style={{position: "absolute", left: 300, top: 300, width: 1320, opacity: chartOn}}>
        <div style={{fontFamily: HEAD, fontSize: 32, fontWeight: HW, letterSpacing: HLS}}>Correct root cause, share of attempts</div>
        <div style={{fontSize: 18, color: C.muted, marginTop: 10}}>Claude Sonnet 5.5 · 8 fault types · 4 attempts per incident</div>
        <div style={{position: "relative", marginTop: 26}}>
          {rows.map(([group, label, ok, n, ours], i) => {
            const share = ok / n;
            const g = tw(s, swap + 0.6 + DELAY[i], 1.0);
            if (group && i) y += 34;
            const top = y + (group ? 34 : 0);
            const out = (
              <React.Fragment key={label}>
                {group && <div style={{position: "absolute", top: y, left: 0, fontSize: 15, fontWeight: 600, letterSpacing: "0.1em", color: C.muted}}>{group.toUpperCase()}</div>}
                <div style={{position: "absolute", top, left: 0, width: 560, textAlign: "right", whiteSpace: "nowrap", fontSize: 18, color: ours ? C.text : C.text2, lineHeight: "30px"}}>{label}</div>
                <div style={{position: "absolute", top: top + 2, left: 590, width: 620 * share * g, height: 26,
                  borderRadius: "0 6px 6px 0", background: ours ? C.accent : "#4a5160"}} />
                <div style={{position: "absolute", top, left: 590 + 620 * share * g + 14, fontSize: 19, lineHeight: "30px", whiteSpace: "nowrap"}}>
                  <b style={{fontVariantNumeric: "tabular-nums"}}>{Math.round(share * g * 100)}%</b>
                  <span style={{color: C.muted, opacity: tw(s, swap + 1.4 + DELAY[i], 0.4)}}> {ok}/{n}</span>
                </div>
              </React.Fragment>
            );
            y = top + 56;
            return out;
          })}
        </div>
      </div>
    </>
  );
};

const End: React.FC<{s: number}> = ({s}) => {
  const out = tw(s, SECONDS - 0.6, 0.6, INOUT);
  return (
    <div style={{position: "absolute", left: 160, top: 380, opacity: 1 - out}}>
      <Rise s={s} at={T.end + 0.2} dy={22} d={0.9}><div style={{fontFamily: HEAD, fontSize: 130, fontWeight: HW, letterSpacing: HLS, lineHeight: 1}}>Pagerless</div></Rise>
      <div style={{fontFamily: MONO, fontSize: 19, color: C.muted, marginTop: 34, opacity: tw(s, T.end + 0.7, 0.8)}}>
        Python · MCP · LangGraph · Claude API · pgvector · Prometheus · OpenTelemetry
      </div>
    </div>
  );
};

export const Pagerless: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const s = frame / fps;
  return (
    <AbsoluteFill style={{background: C.bg, color: C.text, fontFamily: SANS}}>
      <AbsoluteFill style={{background: "radial-gradient(1100px 650px at 12% -8%, rgba(91,156,255,0.09), transparent 65%)"}} />
      <AbsoluteFill style={{backgroundImage: "radial-gradient(rgba(255,255,255,0.045) 1px, transparent 1px)", backgroundSize: "30px 30px",
        maskImage: "radial-gradient(ellipse at 50% 55%, black 30%, transparent 80%)"}} />
      <ServiceMap s={s} />
      {s < 4.2 && <Title s={s} />}
      <Chrome s={s} />
      {s > 4.5 && s < T.alert + 0.1 && <Break s={s} />}
      {s > T.alert && s < T.inv + 0.1 && <Alert s={s} />}
      {s > T.inv && s < T.report + 0.1 && <Investigate s={s} />}
      {s > T.report && s < T.score + 0.1 && <Report s={s} />}
      {s > T.score && s < T.end + 0.1 && <Score s={s} />}
      {s > T.end && <End s={s} />}
    </AbsoluteFill>
  );
};
