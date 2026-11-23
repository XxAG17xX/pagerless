// A 64-second replay of one real Pagerless incident (runs/20261123T204228Z_payment-down):
// every number and finding below comes from that run's truth.json, trace.json and report.json.
import React from "react";
import {AbsoluteFill, Easing, Img, interpolate, Series, staticFile, useCurrentFrame, useVideoConfig} from "remotion";
import truth from "../public/run/truth.json";
import trace from "../public/run/trace.json";
import report from "../public/run/report.json";

const C = {
  bg: "#111110", panel: "#1c1c1b", line: "#33332f", text: "#f0efec", text2: "#c3c2b7", muted: "#8c8b84",
  accent: "#3987e5", red: "#e66767", green: "#0ca30c",
};
const SANS = "'Segoe UI', -apple-system, Helvetica, Arial, sans-serif";
const MONO = "'Cascadia Mono', Consolas, 'Courier New', monospace";
const ease = Easing.bezier(0.16, 1, 0.3, 1);
const clamp = {extrapolateLeft: "clamp", extrapolateRight: "clamp"} as const;

// Fade a whole scene in at its start and out at its end.
const Scene: React.FC<{children: React.ReactNode; length: number}> = ({children, length}) => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{fontFamily: SANS, color: C.text,
      opacity: interpolate(frame, [0, 12, length - 12, length], [0, 1, 1, 0], clamp)}}>
      {children}
    </AbsoluteFill>
  );
};

// Slide-and-fade in, starting `at` seconds into the scene.
const Appear: React.FC<{at: number; children: React.ReactNode; style?: React.CSSProperties}> = ({at, children, style}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  return (
    <div style={{...style, opacity: interpolate(frame, [at * fps, at * fps + 15], [0, 1], clamp),
      translate: interpolate(frame, [at * fps, at * fps + 20], ["0px 24px", "0px 0px"], {...clamp, easing: ease})}}>
      {children}
    </div>
  );
};

const Step: React.FC<{n: number; title: string; sub?: string}> = ({n, title, sub}) => (
  <div style={{position: "absolute", left: 120, top: 90}}>
    <div style={{fontSize: 30, color: C.accent, fontWeight: 600, letterSpacing: "0.08em"}}>STEP {n}</div>
    <div style={{fontSize: 68, fontWeight: 600, marginTop: 6}}>{title}</div>
    {sub && <div style={{fontSize: 36, color: C.text2, marginTop: 10}}>{sub}</div>}
  </div>
);

const utc = (iso: string) => iso.slice(11, 19) + " UTC";

const Title: React.FC = () => (
  <Scene length={120}>
    <AbsoluteFill style={{justifyContent: "center", paddingLeft: 160}}>
      <Appear at={0.2}><div style={{fontSize: 150, fontWeight: 700, letterSpacing: "-0.02em"}}>Pagerless</div></Appear>
      <Appear at={0.7}><div style={{fontSize: 52, color: C.text2, marginTop: 12, maxWidth: 1700}}>
        An AI on-call engineer, tested by breaking a real system on purpose.</div></Appear>
      <Appear at={1.4}><div style={{fontSize: 32, color: C.muted, marginTop: 40}}>
        One real incident, replayed from its run files · Claude Sonnet 5.5</div></Appear>
    </AbsoluteFill>
  </Scene>
);

const Break: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const cmd = "docker stop payment";
  const typed = cmd.slice(0, Math.floor(interpolate(frame, [0.8 * fps, 2.2 * fps], [0, cmd.length], clamp)));
  return (
    <Scene length={180}>
      <Step n={1} title="Break the shop on purpose" sub="The OpenTelemetry Demo: a borrowed 20-service web shop" />
      <div style={{position: "absolute", left: 120, top: 400, width: 1080, background: C.panel, borderRadius: 18,
        border: `1px solid ${C.line}`, padding: "36px 44px", fontFamily: MONO, fontSize: 40}}>
        <div style={{color: C.muted, fontSize: 28, marginBottom: 18}}>faults/inject.py · {utc(truth.injected_at)}</div>
        <div><span style={{color: C.accent}}>$ </span>{typed}<span style={{opacity: frame % 30 < 15 ? 1 : 0}}>▌</span></div>
        {frame > 2.6 * fps && <div style={{color: C.text2, marginTop: 10}}>payment</div>}
      </div>
      <Appear at={3.2} style={{position: "absolute", left: 1280, top: 430, width: 520}}>
        <div style={{fontSize: 30, color: C.muted}}>Answer key, hidden from the agent</div>
        <div style={{fontSize: 64, fontWeight: 600, marginTop: 8}}>root cause: {truth.root_cause_service}</div>
      </Appear>
    </Scene>
  );
};

const Alert: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const shots = ["alerts-healthy", "alerts-pending", "alerts-firing"];
  return (
    <Scene length={240}>
      <Step n={2} title="My alert fires" sub={`${truth.seconds_to_alert} s after the break: ${truth.alerts.join(", ")}`} />
      <div style={{position: "absolute", left: 120, top: 330, width: 1680, height: 640, borderRadius: 16, overflow: "hidden",
        border: `1px solid ${C.line}`}}>
        {shots.map((s, i) => (
          <Img key={s} src={staticFile(`shots/${s}.png`)} style={{position: "absolute", width: 1680, top: -40,
            opacity: i === 0 ? 1 : interpolate(frame, [(i * 2.4) * fps, (i * 2.4 + 0.5) * fps], [0, 1], clamp)}} />
        ))}
      </div>
      <Appear at={5.4} style={{position: "absolute", right: 120, top: 120, fontSize: 34, color: C.red, fontWeight: 600}}>
        ● FIRING
      </Appear>
    </Scene>
  );
};

// The 8 tool calls, in order, with a one-line reading of each real output.
const READINGS = [
  "CheckoutFailing and ServiceErrors are firing",
  "errors in checkout, frontend, frontend-proxy; none from payment",
  "5 failing checkout traces",
  "no error logs from checkout",
  "checkout → payment: 'name resolver error: produced zero addresses'",
  "17 services known to Jaeger",
  "payment request rate: 0",
  "last payment log at 20:42:00, then silence",
];
const KIND: Record<string, [string, string]> = {prometheus: ["METRICS", C.accent], jaeger: ["TRACES", "#d55181"], logs: ["LOGS", "#c98500"]};

const Investigate: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  return (
    <Scene length={600}>
      <Step n={3} title="The agent investigates through MCP" sub="Read-only tools over metrics, traces and logs" />
      <div style={{position: "absolute", left: 120, top: 320, width: 1100}}>
        {trace.steps.map((s, i) => {
          const [tag, color] = KIND[s.tool.split("_")[0]];
          return (
            <Appear key={i} at={0.6 + i * 1.9} style={{display: "flex", alignItems: "baseline", gap: 22, marginBottom: 14}}>
              <span style={{fontSize: 20, fontWeight: 700, color, width: 96, flexShrink: 0, letterSpacing: "0.06em"}}>{tag}</span>
              <div>
                <div style={{fontFamily: MONO, fontSize: 22, color: C.muted}}>{s.tool}</div>
                <div style={{fontSize: 28, color: i === 4 ? C.red : C.text}}>{READINGS[i]}</div>
              </div>
            </Appear>
          );
        })}
      </div>
      <div style={{position: "absolute", left: 1260, top: 330, width: 540, height: 600, borderRadius: 16, overflow: "hidden",
        border: `1px solid ${C.line}`, opacity: interpolate(frame, [9 * fps, 10 * fps], [0, 1], clamp)}}>
        <Img src={staticFile("shots/jaeger-failing-trace.png")} style={{position: "absolute", height: 600, left: -150,
          scale: interpolate(frame, [9 * fps, 20 * fps], [1, 1.12], clamp)}} />
      </div>
      <Appear at={16} style={{position: "absolute", left: 1260, top: 960, fontSize: 30, color: C.text2, fontFamily: MONO}}>
        {trace.tool_calls} tool calls · {trace.seconds} s · ${trace.cost_usd.toFixed(3)}
      </Appear>
    </Scene>
  );
};

const Report: React.FC = () => {
  const frame = useCurrentFrame();
  const evidence = [report.evidence[2].finding, report.evidence[3].finding, report.evidence[4].finding.split(", which")[0]];
  return (
    <Scene length={360}>
      <Step n={4} title="A cited report, and a human decides" />
      <div style={{position: "absolute", left: 120, top: 270, width: 1680, background: C.panel, borderRadius: 18,
        border: `1px solid ${C.line}`, padding: "40px 52px"}}>
        <Appear at={0.3}><div style={{fontSize: 30, color: C.muted}}>Root cause</div>
          <div style={{fontSize: 84, fontWeight: 700, color: C.text}}>{report.root_cause_service}
            <span style={{fontSize: 34, color: C.muted, fontWeight: 400}}>   confidence {report.confidence}</span></div></Appear>
        <div style={{marginTop: 22}}>
          {evidence.map((e, i) => (
            <Appear key={i} at={1.2 + i * 1.1}><div style={{fontSize: 30, color: C.text2, marginTop: 14, lineHeight: 1.35}}>
              <span style={{color: C.accent}}>evidence {i + 1} </span>{e}</div></Appear>
          ))}
        </div>
        <Appear at={5}><div style={{fontSize: 30, marginTop: 30}}><span style={{color: C.muted}}>suggested fix  </span>
          <span style={{fontFamily: MONO}}>docker compose up -d payment</span></div></Appear>
      </div>
      <Appear at={6.5} style={{position: "absolute", left: 120, top: 900, fontSize: 40, fontFamily: MONO}}>
        Apply this fix? <span style={{color: C.text2}}>[y = approve, n = reject]</span>
        <span style={{opacity: frame % 30 < 15 ? 1 : 0}}> ▌</span>
      </Appear>
    </Scene>
  );
};

const Score: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  return (
    <Scene length={270}>
      <Step n={5} title="Scored against the answer key" />
      <Appear at={0.4} style={{position: "absolute", left: 120, top: 280, fontSize: 42}}>
        Agent said <b>{report.root_cause_service}</b> <span style={{color: C.green}}>✓ correct</span>
      </Appear>
      <Appear at={1.2} style={{position: "absolute", left: 820, top: 280, fontSize: 42, color: C.text2}}>
        Rules runbook said <b style={{color: C.text}}>{truth.baseline.root_cause_service}</b> <span style={{color: C.red}}>✗ wrong</span>
      </Appear>
      <Img src={staticFile("shots/results-dark.svg")} style={{position: "absolute", left: 120, top: 400, width: 1160,
        opacity: interpolate(frame, [2.4 * fps, 3.2 * fps], [0, 1], clamp)}} />
      <Appear at={4} style={{position: "absolute", left: 1340, top: 430, width: 460, fontSize: 32, color: C.text2, lineHeight: 1.4}}>
        Across 8 fault types: <b style={{color: C.text}}>85%</b> correct vs <b style={{color: C.text}}>11%</b> for a rules runbook.
        <br /><br />Under prompt injection: <b style={{color: C.text}}>2/8</b> without the defence, <b style={{color: C.text}}>8/8</b> with it.
      </Appear>
    </Scene>
  );
};

const End: React.FC = () => (
  <Scene length={150}>
    <AbsoluteFill style={{justifyContent: "center", paddingLeft: 160}}>
      <Appear at={0.2}><div style={{fontSize: 120, fontWeight: 700}}>Pagerless</div></Appear>
      <Appear at={0.6}><div style={{fontSize: 38, color: C.text2, marginTop: 16}}>
        Python · MCP · LangGraph · Claude API · pgvector · Prometheus · OpenTelemetry</div></Appear>
      <Appear at={1.1}><div style={{fontSize: 30, color: C.muted, marginTop: 40}}>
        Built with Claude Code. The OpenTelemetry Demo is borrowed; the agent, MCP servers, harness and scoring are mine.</div></Appear>
    </AbsoluteFill>
  </Scene>
);

export const Pagerless: React.FC = () => (
  <AbsoluteFill style={{background: C.bg}}>
  <Series>
    <Series.Sequence durationInFrames={120}><Title /></Series.Sequence>
    <Series.Sequence durationInFrames={180}><Break /></Series.Sequence>
    <Series.Sequence durationInFrames={240}><Alert /></Series.Sequence>
    <Series.Sequence durationInFrames={600}><Investigate /></Series.Sequence>
    <Series.Sequence durationInFrames={360}><Report /></Series.Sequence>
    <Series.Sequence durationInFrames={270}><Score /></Series.Sequence>
    <Series.Sequence durationInFrames={150}><End /></Series.Sequence>
  </Series>
  </AbsoluteFill>
);
