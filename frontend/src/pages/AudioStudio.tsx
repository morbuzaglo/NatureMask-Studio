import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../services/api";
import { useStudio } from "../hooks/useStudio";
import { TriPlayer, type StreamName } from "../audio/engine";
import { Badge, Empty, Notice, PageHeader, Panel, Slider } from "../components/ui";

const LABEL: Record<StreamName, string> = { target: "Machine only", masker: "Soundscape only", mix: "Machine + soundscape" };
const COLOR: Record<StreamName, string> = { target: "var(--target)", masker: "var(--masker)", mix: "var(--mix)" };

export default function AudioStudio() {
  const { project, toast } = useStudio();
  const nav = useNavigate();
  const player = useRef<TriPlayer | null>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const [ready, setReady] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [active, setActive] = useState<StreamName>("mix");
  const [vol, setVol] = useState(0.8);
  const [pos, setPos] = useState(0);
  const [loop, setLoop] = useState(true);
  const render = project?.render;

  useEffect(() => {
    if (!project || !render) return;
    const p = new TriPlayer();
    player.current = p;
    setReady(false);
    p.load({ target: api.audioUrl(project.id, "target", render.created), masker: api.audioUrl(project.id, "masker", render.created), mix: api.audioUrl(project.id, "mix", render.created) })
      .then(() => { setReady(true); draw(); })
      .catch((e) => toast(e.message, "error"));
    p.onEnded = () => setPlaying(false);
    return () => { p.stop(); p.ctx.close(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project?.id, render?.created]);

  useEffect(() => {
    let raf = 0;
    const tick = () => { if (player.current) { setPos(player.current.position); draw(); } raf = requestAnimationFrame(tick); };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  });

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement).tagName === "INPUT") return;
      if (e.key === " ") { e.preventDefault(); toggle(); }
      if (e.key === "1") select("target");
      if (e.key === "2") select("masker");
      if (e.key === "3") select("mix");
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  function draw() {
    const p = player.current, cv = canvas.current;
    if (!p || !cv || !p.buffers.mix) return;
    const dpr = window.devicePixelRatio || 1;
    const w = cv.clientWidth, h = cv.clientHeight;
    if (cv.width !== w * dpr) { cv.width = w * dpr; cv.height = h * dpr; }
    const g = cv.getContext("2d")!;
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, w, h);
    const cs = getComputedStyle(document.documentElement);
    const rows: StreamName[] = ["target", "masker", "mix"];
    rows.forEach((r, ri) => {
      const pk = p.peaks(r, Math.floor(w));
      const y0 = (h / 3) * ri, hh = h / 3;
      g.fillStyle = cs.getPropertyValue(`--${r}`).trim();
      g.globalAlpha = r === active ? 0.95 : 0.35;
      for (let i = 0; i < pk.max.length; i++) {
        const a = y0 + hh / 2 - (pk.max[i] * hh) / 2, b = y0 + hh / 2 - (pk.min[i] * hh) / 2;
        g.fillRect(i, a, 1, Math.max(1, b - a));
      }
    });
    g.globalAlpha = 1;
    const x = (p.position / Math.max(p.duration, 1e-6)) * w;
    g.fillStyle = cs.getPropertyValue("--text").trim();
    g.fillRect(x, 0, 1.5, h);
  }

  function select(s: StreamName) { player.current?.select(s); setActive(s); }
  async function toggle() {
    const p = player.current;
    if (!p || !ready) return;
    if (p.playing) { p.pause(); setPlaying(false); } else { await p.play(); setPlaying(true); }
  }
  function seek(e: React.MouseEvent<HTMLCanvasElement>) {
    const p = player.current; if (!p) return;
    const r = e.currentTarget.getBoundingClientRect();
    p.seek(((e.clientX - r.left) / r.width) * p.duration);
  }

  if (!project) return <Empty title="No project open">Create or open a project on the Dashboard first.</Empty>;
  if (!render) return <Empty title="Nothing rendered yet">Generate a soundscape in the Masking Laboratory first.<div className="mt-4"><button className="btn" onClick={() => nav("/masking")}>Masking Laboratory</button></div></Empty>;

  return (
    <div>
      <PageHeader step="Step 4" title="Audio studio" sub="Three sample-aligned streams. Switching is instant and click-free, so you hear exactly what the soundscape changes. Keys: 1 · 2 · 3 and Space."
        right={<button className="btn btn-primary" onClick={() => nav("/export")}>Next: export →</button>} />
      {project.target?.kind === "spectrum" && <div className="mb-4"><Notice tone="accent">The machine stream is a <b>synthetic approximation</b> reconstructed from spectrum data — not a recording of the actual machine.</Notice></div>}
      {render.target_source.looped && <div className="mb-4"><Notice>The machine recording is shorter than the soundscape and is looped in the preview.</Notice></div>}
      <Panel>
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <button className="btn btn-primary !px-5" onClick={toggle} disabled={!ready} aria-label={playing ? "Pause" : "Play"}>
            {playing ? <svg width="14" height="14" viewBox="0 0 14 14"><rect x="2" y="1" width="3.5" height="12" fill="currentColor" /><rect x="8.5" y="1" width="3.5" height="12" fill="currentColor" /></svg>
              : <svg width="14" height="14" viewBox="0 0 14 14"><path d="M3 1l10 6-10 6z" fill="currentColor" /></svg>}
            {ready ? (playing ? "Pause" : "Play") : "Loading…"}
          </button>
          {(Object.keys(LABEL) as StreamName[]).map((s, i) => (
            <button key={s} onClick={() => select(s)} className="btn" aria-pressed={active === s}
              style={active === s ? { borderColor: COLOR[s], boxShadow: `inset 0 0 0 1px ${COLOR[s]}`, color: COLOR[s] } : undefined}>
              <span className="num text-[11px] text-faint">{i + 1}</span>{LABEL[s]}
            </button>
          ))}
          <label className="ml-auto flex items-center gap-2 text-[13px]"><input type="checkbox" checked={loop} onChange={(e) => { setLoop(e.target.checked); if (player.current) player.current.loop = e.target.checked; }} />Loop</label>
          <div className="w-44"><Slider label="Volume" value={vol} min={0} max={1} step={0.01} onChange={(v) => { setVol(v); player.current?.setVolume(v); }} /></div>
        </div>
        <canvas ref={canvas} onClick={seek} className="h-48 w-full cursor-pointer rounded-lg border border-line bg-panel-2" aria-label="Waveforms; click to seek" />
        <div className="mt-2 flex justify-between text-[12px] text-faint"><span className="num">{pos.toFixed(1)} s</span><span>preview {render.preview_s.toFixed(0)} s of {render.duration_s.toFixed(0)} s · {render.fs / 1000} kHz · seed {render.seed}</span></div>
        <p className="mt-3 text-[12px] text-faint">All three previews share one normalisation gain, so their relative levels are true to the design. Absolute loudness depends on your playback volume{project.target?.calibrated ? " — calibrate playback to hear design SPL" : ""}.</p>
      </Panel>
      <div className="mt-5 grid grid-cols-1 gap-5 lg:grid-cols-2">
        <BlindTest player={player} ready={ready} />
        <Panel title="How to listen">
          <ul className="list-disc space-y-1.5 pl-5 text-[13px] text-muted">
            <li>Start with <b className="text-text">Machine only</b>, then switch to <b className="text-text">Machine + soundscape</b> at the same moment. Ask: does the machine still stand out?</li>
            <li>Listen for tones (whine, hum): they are usually the last thing to disappear.</li>
            <li>Check <b className="text-text">Soundscape only</b> for naturalness — repetition, harshness or anything that draws attention.</li>
            <li>Use headphones or the real playback system at a comfortable, fixed volume.</li>
          </ul>
        </Panel>
      </div>
    </div>
  );
}

function BlindTest({ player, ready }: { player: React.MutableRefObject<TriPlayer | null>; ready: boolean }) {
  const [x, setX] = useState<StreamName | null>(null);
  const [score, setScore] = useState({ n: 0, correct: 0 });
  const [last, setLast] = useState<string>("");
  async function trial() {
    const p = player.current; if (!p) return;
    const pick: StreamName = Math.random() < 0.5 ? "masker" : "mix";
    setX(pick); setLast("");
    p.select(pick);
    await p.play(Math.random() * Math.max(0, p.duration - 6));
  }
  function answer(a: StreamName) {
    if (!x) return;
    const ok = a === x;
    setScore((s) => ({ n: s.n + 1, correct: s.correct + (ok ? 1 : 0) }));
    setLast(ok ? "Correct" : `Not quite: it was “${LABEL[x]}”`);
    setX(null);
    player.current?.pause();
  }
  // Binomial chance probability of >= correct out of n with p = 0.5
  const pChance = (() => { let s = 0; const { n, correct } = score; for (let k = correct; k <= n; k++) s += comb(n, k) / 2 ** n; return s; })();
  return (
    <Panel title="Blind test: can you hear the machine?" right={<Badge>{score.correct}/{score.n}</Badge>}>
      <p className="text-[13px] text-muted">A random excerpt plays either the soundscape alone or the soundscape with the machine. Decide whether the machine is present. Consistently correct answers mean the machine is still detectable; chance-level answers (about half right) suggest it is effectively masked for you.</p>
      <div className="mt-3 flex flex-wrap gap-2">
        <button className="btn btn-primary" disabled={!ready || !!x} onClick={trial}>Play random excerpt</button>
        <button className="btn" disabled={!x} onClick={() => answer("mix")}>Machine present</button>
        <button className="btn" disabled={!x} onClick={() => answer("masker")}>No machine</button>
        <button className="btn btn-ghost" onClick={() => { setScore({ n: 0, correct: 0 }); setLast(""); }}>Reset</button>
      </div>
      {last && <div className="mt-2 text-[13px]">{last}</div>}
      {score.n >= 5 && <div className="mt-2 text-[12px] text-faint">Probability of scoring ≥ {score.correct}/{score.n} by guessing: {(pChance * 100).toFixed(1)} %</div>}
    </Panel>
  );
}

function comb(n: number, k: number) { let r = 1; for (let i = 1; i <= k; i++) r = (r * (n - k + i)) / i; return r; }
