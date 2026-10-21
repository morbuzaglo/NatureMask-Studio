import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type SceneConfig, type SceneModule } from "../services/api";
import { useStudio } from "../hooks/useStudio";
import { Badge, Empty, Field, Notice, PageHeader, Panel, Slider } from "../components/ui";

const PARAMS: Record<string, { key: string; label: string; min: number; max: number; step: number }[]> = {
  birds: [{ key: "activity", label: "Activity", min: 0, max: 1, step: 0.05 }, { key: "pitch", label: "Pitch scale", min: 0.7, max: 1.3, step: 0.05 }, { key: "distance", label: "Distance", min: 0, max: 1, step: 0.05 }],
  wind: [{ key: "strength", label: "Strength", min: 0, max: 1, step: 0.05 }, { key: "gustiness", label: "Gustiness", min: 0, max: 1, step: 0.05 }],
  leaves: [{ key: "activity", label: "Activity", min: 0, max: 1, step: 0.05 }],
  grass: [{ key: "activity", label: "Activity", min: 0, max: 1, step: 0.05 }],
  stream: [{ key: "flow", label: "Flow", min: 0, max: 1, step: 0.05 }],
  waterfall: [{ key: "flow", label: "Flow", min: 0, max: 1, step: 0.05 }],
  rain: [{ key: "intensity", label: "Intensity", min: 0, max: 1, step: 0.05 }],
  drips: [{ key: "rate", label: "Drips / s", min: 0.1, max: 6, step: 0.1 }],
  waves: [{ key: "size", label: "Wave size", min: 0, max: 1, step: 0.05 }],
  crickets: [{ key: "temperature_c", label: "Temperature °C (chirp rate)", min: 5, max: 35, step: 1 }, { key: "density", label: "Density", min: 0, max: 1, step: 0.05 }],
  night_insects: [{ key: "density", label: "Density", min: 0, max: 1, step: 0.05 }],
  cicadas: [{ key: "intensity", label: "Intensity", min: 0, max: 1, step: 0.05 }],
  frogs: [{ key: "activity", label: "Activity", min: 0, max: 1, step: 0.05 }],
  owl: [{ key: "rate", label: "Calls / s", min: 0, max: 0.3, step: 0.01 }],
  woodpecker: [{ key: "rate", label: "Drums / s", min: 0, max: 0.3, step: 0.01 }],
  ambience: [],
};
const MIX = "__mix__";
const DEFAULTS: Record<string, number> = { activity: 0.5, pitch: 1, distance: 0.3, strength: 0.5, gustiness: 0.5, flow: 0.5, intensity: 0.5, rate: 0.05, size: 0.5, temperature_c: 22, density: 0.6 };

export default function Soundscape() {
  const { project, catalog, refresh, toast, mode } = useStudio();
  const nav = useNavigate();
  const [scene, setScene] = useState<SceneConfig | null>(project?.scene ?? null);
  const [mods, setMods] = useState<{ season: string; time_of_day: string; weather: string }>({ season: project?.scene?.season || "", time_of_day: project?.scene?.time_of_day || "", weather: project?.scene?.weather || "" });
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [settings, setSettings] = useState(project?.settings);
  useEffect(() => { setScene(project?.scene ?? null); setSettings(project?.settings); }, [project?.id]);
  // audition: MIX (all enabled sources) or one source id, looped; edits re-render and resume in place
  const audio = useRef<HTMLAudioElement | null>(null);
  const reqId = useRef(0);
  const [playing, setPlaying] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  useEffect(() => stop, [project?.id]);
  const modsKey = JSON.stringify(scene?.modules ?? []);
  useEffect(() => {
    if (!playing) return;
    if (playing !== MIX && !scene?.modules.some((m) => m.id === playing)) { stop(); return; }
    const t = setTimeout(() => play(playing, audio.current?.currentTime ?? 0), 400);
    return () => clearTimeout(t);
  }, [modsKey]);
  if (!project || !catalog) return <Empty title="No project open">Create or open a project on the Dashboard first.</Empty>;

  async function choose(preset: string, m = mods) {
    setBusy(true);
    try {
      const s = await api.setScene(project!.id, { preset, season: m.season || null, time_of_day: m.time_of_day || null, weather: m.weather || null });
      setScene(s); setDirty(false); await refresh();
    } catch (e: any) { toast(e.message, "error"); } finally { setBusy(false); }
  }
  async function saveModules() {
    if (!scene) return;
    setBusy(true);
    try {
      const s = await api.setScene(project!.id, { modules: scene.modules });
      setScene(s); setDirty(false); await refresh(); toast("Environment saved", "success");
    } catch (e: any) { toast(e.message, "error"); } finally { setBusy(false); }
  }
  async function saveSettings(patch: any) {
    const ns = { ...settings!, ...patch };
    setSettings(ns);
    try { await api.patchProject(project!.id, { settings: patch }); await refresh(); } catch (e: any) { toast(e.message, "error"); }
  }
  function stop() {
    reqId.current++;
    if (audio.current) { audio.current.pause(); URL.revokeObjectURL(audio.current.src); audio.current = null; }
    setPlaying(null); setLoading(false);
  }
  async function play(what: string, resumeAt = 0) {
    if (!scene) return;
    const id = ++reqId.current;
    setPlaying(what); setLoading(true);
    try {
      const { blob, silent } = await api.audition(project!.id, scene.modules, what === MIX ? null : what);
      if (id !== reqId.current) return;
      const a = new Audio(URL.createObjectURL(blob));
      a.loop = true;
      a.addEventListener("loadedmetadata", () => { a.currentTime = resumeAt % (a.duration || 1); }, { once: true });
      if (audio.current) { audio.current.pause(); URL.revokeObjectURL(audio.current.src); }
      audio.current = a;
      await a.play();
      if (silent && resumeAt === 0) toast(what === MIX ? "The enabled sources are silent in this excerpt." : `${label(scene.modules.find((m) => m.id === what)!.type)} makes no sound in this 20 s excerpt — raise its rate or activity.`, "info");
    } catch (e: any) {
      if (id === reqId.current) { toast(e.message, "error"); stop(); }
    } finally { if (id === reqId.current) setLoading(false); }
  }
  const toggle = (what: string) => (playing === what ? stop() : play(what));
  const playIcon = (what: string) => (playing !== what ? "▶" : loading ? "…" : "■");
  const update = (i: number, m: Partial<SceneModule>) => { if (!scene) return; const ms = [...scene.modules]; ms[i] = { ...ms[i], ...m }; setScene({ ...scene, modules: ms }); setDirty(true); };
  const addModule = (type: string) => { if (!scene) return; setScene({ ...scene, modules: [...scene.modules, { id: `${type}_${Date.now() % 100000}`, type, enabled: true, level_db: -6, params: {} }] }); setDirty(true); };
  const label = (t: string) => catalog.modules.find((m) => m.type === t)?.label || t;

  return (
    <div>
      <PageHeader step="Step 2" title="Soundscape designer" sub="Choose a natural environment. Each preset is a plausible combination of procedural sound sources — no loops, no stock recordings."
        right={scene && <button className="btn btn-primary" onClick={() => nav("/masking")} disabled={dirty}>Next: masking →</button>} />
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {catalog.presets.map((p) => (
          <button key={p.id} disabled={busy} onClick={() => choose(p.id)}
            className="panel p-4 text-left transition-colors hover:border-[var(--accent)]"
            style={scene?.preset === p.id ? { borderColor: "var(--accent)", boxShadow: "inset 0 0 0 1px var(--accent)" } : undefined}>
            <div className="font-semibold">{p.name}</div>
            <div className="mt-1 text-[12.5px] leading-snug text-muted">{p.description}</div>
            <div className="mt-3 flex flex-wrap gap-1">{[...new Set(p.modules)].map((m) => <span key={m} className="chip !text-[10.5px]">{label(m)}</span>)}</div>
          </button>
        ))}
      </div>
      <div className="mt-5 grid grid-cols-1 gap-4 md:grid-cols-3">
        {(["season", "time_of_day", "weather"] as const).map((k) => (
          <Field key={k} label={k.replaceAll("_", " ")}>
            <select className="input" value={mods[k]} disabled={!scene} onChange={(e) => { const m = { ...mods, [k]: e.target.value }; setMods(m); if (scene) choose(scene.preset, m); }}>
              <option value="">— default —</option>{(catalog.modifiers[k] || []).map((o) => <option key={o} value={o}>{o.replaceAll("_", " ")}</option>)}
            </select>
          </Field>
        ))}
      </div>
      {scene && (
        <div className="mt-6 grid grid-cols-1 gap-5 xl:grid-cols-[1.5fr_1fr]">
          <Panel title={`Sound sources · ${scene.name}`} right={<div className="flex gap-2">
            <select className="input !w-44" value="" onChange={(e) => e.target.value && addModule(e.target.value)} aria-label="Add sound source">
              <option value="">+ Add source…</option>{catalog.modules.map((m) => <option key={m.type} value={m.type}>{m.label}</option>)}</select>
            <button className="btn" disabled={scene.modules.length === 0} onClick={() => toggle(MIX)} title="Listen to all enabled sources together (20 s loop)">{playIcon(MIX)} {playing === MIX ? "Stop" : "Play mix"}</button>
            <button className="btn btn-primary" disabled={!dirty || busy} onClick={saveModules}>Save changes</button></div>}>
            {scene.modules.length === 0 && <p className="text-muted">No sources yet — add one above.</p>}
            <div className="space-y-2">
              {scene.modules.map((m, i) => {
                const meta = catalog.modules.find((x) => x.type === m.type);
                return (
                  <div key={m.id} className="rounded-lg border border-line bg-panel-2 p-3" style={{ opacity: m.enabled ? 1 : 0.5 }}>
                    <div className="flex flex-wrap items-center gap-3">
                      <input type="checkbox" checked={m.enabled} onChange={(e) => update(i, { enabled: e.target.checked })} aria-label={`Enable ${label(m.type)}`} />
                      <button className="btn btn-ghost !w-8 !px-0 !py-1" onClick={() => toggle(m.id)} aria-label={`${playing === m.id ? "Stop" : "Play"} ${label(m.type)}`} title="Listen to this source alone (20 s loop)"
                        style={playing === m.id ? { color: "var(--accent)" } : undefined}>{playIcon(m.id)}</button>
                      <span className="min-w-[150px] font-semibold">{label(m.type)}</span>
                      {meta?.is_bed ? <Badge tone="masker">broadband bed</Badge> : <Badge>events</Badge>}
                      {(meta?.tonal_fraction ?? 0) > 0.5 && <Badge tone="warn">tonal</Badge>}
                      <div className="ml-auto w-56"><Slider label="Level" unit=" dB" value={m.level_db} min={-36} max={6} step={1} onChange={(v) => update(i, { level_db: v })} /></div>
                      <button className="btn btn-ghost !px-2 !py-1 text-[12px]" onClick={() => { setScene({ ...scene, modules: scene.modules.filter((_, j) => j !== i) }); setDirty(true); }}>Remove</button>
                    </div>
                    {mode === "expert" && (PARAMS[m.type] || []).length > 0 && (
                      <div className="mt-3 grid grid-cols-1 gap-3 pl-7 md:grid-cols-3">
                        {PARAMS[m.type].map((p) => (
                          <Slider key={p.key} label={p.label} min={p.min} max={p.max} step={p.step}
                            value={Number(m.params[p.key] ?? DEFAULTS[p.key] ?? p.min)} onChange={(v) => update(i, { params: { ...m.params, [p.key]: v } })} />
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
            <p className="mt-3 text-[12px] text-faint">▶ plays one source alone, "Play mix" plays all enabled sources — both at the balance set by the level sliders, before the Masking Laboratory sets the overall level. Changes are heard as you make them.</p>
            {mode === "beginner" && <p className="mt-1 text-[12px] text-faint">Switch to Expert mode (sidebar) for per-source parameters such as bird activity, wind gustiness or cricket temperature.</p>}
          </Panel>
          <div className="space-y-4">
            <Panel title="Generation settings">
              {settings && (
                <div className="grid grid-cols-2 gap-3">
                  <Field label="Duration (s)" hint="Min 10 s; minutes are fine"><input className="input" type="number" min={10} value={settings.duration_s} onChange={(e) => saveSettings({ duration_s: Math.max(10, +e.target.value) })} /></Field>
                  <Field label="Sample rate"><select className="input" value={settings.fs} onChange={(e) => saveSettings({ fs: +e.target.value })}><option value={44100}>44.1 kHz</option><option value={48000}>48 kHz</option><option value={96000}>96 kHz</option></select></Field>
                  <Field label="Random seed" hint="Same seed = identical audio"><input className="input" type="number" value={settings.seed} onChange={(e) => saveSettings({ seed: parseInt(e.target.value) || 0 })} /></Field>
                  <Field label="Preview length (s)"><input className="input" type="number" min={10} value={settings.preview_s} onChange={(e) => saveSettings({ preview_s: Math.max(10, +e.target.value) })} /></Field>
                  <label className="col-span-2 flex items-center gap-2 text-[13px]"><input type="checkbox" checked={settings.loop} onChange={(e) => saveSettings({ loop: e.target.checked })} />Seamless loop (crossfade {settings.loop_crossfade_s} s)</label>
                  <label className="col-span-2 flex items-center gap-2 text-[13px]"><input type="checkbox" checked={settings.adaptive} onChange={(e) => saveSettings({ adaptive: e.target.checked })} />Adapt slowly to the machine's level (recordings only)</label>
                  {mode === "expert" && settings.adaptive && <div className="col-span-2"><Slider label="Adaptation depth" unit=" dB" value={settings.adapt_depth_db} min={0} max={12} step={1} onChange={(v) => saveSettings({ adapt_depth_db: v })} /></div>}
                </div>
              )}
            </Panel>
            <Notice tone="accent">Levels here set the <b>balance</b> between sources. The Masking Laboratory then sets the overall level and fine-tunes the balance against your machine.</Notice>
          </div>
        </div>
      )}
    </div>
  );
}
