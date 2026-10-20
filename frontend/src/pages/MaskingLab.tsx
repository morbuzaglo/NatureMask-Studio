import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, waitJob, type Evaluation, type OptResult } from "../services/api";
import { fmt, signed, useStudio } from "../hooks/useStudio";
import { Badge, Empty, Field, Notice, PageHeader, Panel, Progress, Slider, Stat, Tabs, Term } from "../components/ui";
import { C, Plot, logFreqAxis } from "../charts/Plot";

const OBJ = [
  { id: "balanced", name: "Balance masking & naturalness", d: "Default. Reduces prominence while keeping added level and EQ moderate." },
  { id: "max_masking", name: "Maximum predicted masking", d: "Pushes towards full masking — usually needs much more sound." },
  { id: "min_added_spl", name: "Minimum additional SPL", d: "Adds as little sound as possible; masking is partial." },
  { id: "max_naturalness", name: "Maximum naturalness", d: "Keeps the preset's natural balance; no spectral shaping." },
  { id: "custom", name: "Custom weights", d: "Set w1 (masking), w2 (added level), w3 (unnaturalness)." },
];

export default function MaskingLab() {
  const { project, refresh, toast, mode } = useStudio();
  const nav = useNavigate();
  const s = project?.settings;
  const [objective, setObjective] = useState(s?.objective || "balanced");
  const [w, setW] = useState<number[]>(s?.weights || [1, 1, 0.5]);
  const [cap, setCap] = useState<number | null>(s?.masker_cap_rel_db ?? 3);
  const [maxMix, setMaxMix] = useState<string>(s?.max_mix_la != null ? String(s.max_mix_la) : "");
  const [margin, setMargin] = useState(s?.margin_db ?? 3);
  const [k, setK] = useState(s?.k_db ?? -4);
  const [eq, setEq] = useState(s?.allow_eq ?? true);
  const [pareto, setPareto] = useState(false);
  const [opt, setOpt] = useState<OptResult | null>(project?.optimization ?? null);
  const [busy, setBusy] = useState(false);
  const [gen, setGen] = useState<{ p: number; msg: string } | null>(null);
  const [ev, setEv] = useState<Evaluation | null>(null);
  const [view, setView] = useState<"erb" | "third" | "octave" | "psd">("erb");

  useEffect(() => {
    setOpt(project?.optimization ?? null);
    if (project?.render) api.evaluation(project.id).then((r) => setEv(r.evaluation)).catch(() => setEv(null));
    else setEv(null);
  }, [project?.id, project?.render?.created]);

  if (!project) return <Empty title="No project open">Create or open a project on the Dashboard first.</Empty>;
  if (!project.target || !project.scene) return (
    <Empty title="Target and environment needed">
      Define the target noise (step 1) and choose an environment (step 2) first.
      <div className="mt-4 flex justify-center gap-2"><button className="btn" onClick={() => nav("/target")}>Target noise</button><button className="btn" onClick={() => nav("/soundscape")}>Environment</button></div>
    </Empty>);

  async function run() {
    setBusy(true);
    try {
      const settings = { objective, weights: w, masker_cap_rel_db: cap, max_mix_la: maxMix ? parseFloat(maxMix) : null, margin_db: margin, k_db: k, allow_eq: eq };
      await api.patchProject(project!.id, { settings });
      const r = await api.optimize(project!.id, { ...settings, pareto });
      setOpt(r);
      await refresh();
      toast(`Optimised in ${r.solver.seconds.toFixed(1)} s`, "success");
    } catch (e: any) { toast(e.message, "error"); } finally { setBusy(false); }
  }

  async function generate() {
    setGen({ p: 0, msg: "Starting" });
    try {
      const { job } = await api.generate(project!.id);
      await waitJob(job, (j) => setGen({ p: j.progress, msg: j.message }));
      await refresh();
      const r = await api.evaluation(project!.id);
      setEv(r.evaluation);
      toast("Soundscape generated — listen in the Audio Studio", "success");
    } catch (e: any) { toast(e.message, "error"); } finally { setGen(null); }
  }

  const unit = opt?.levels.unit.includes("relative") ? "dB(A) rel" : "dB(A)";
  return (
    <div>
      <PageHeader step="Step 3" title="Masking laboratory"
        sub="The optimiser sets the soundscape level, the balance of its sources and gentle spectral shaping so that the machine's energy is covered in the auditory bands where it is audible — subject to your level limits."
        right={ev && <button className="btn btn-primary" onClick={() => nav("/studio")}>Next: listen →</button>} />
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[360px_1fr]">
        <div className="space-y-4">
          <Panel title={<Term k="objective">Optimisation objective</Term>}>
            <div className="space-y-2">
              {OBJ.map((o) => (
                <label key={o.id} className="flex cursor-pointer gap-3 rounded-lg border p-2.5" style={{ borderColor: objective === o.id ? "var(--accent)" : "var(--line)" }}>
                  <input type="radio" name="obj" checked={objective === o.id} onChange={() => setObjective(o.id)} className="mt-1" />
                  <span><span className="block font-semibold">{o.name}</span><span className="block text-[12px] text-muted">{o.d}</span></span>
                </label>
              ))}
            </div>
            {objective === "custom" && (
              <div className="mt-3 space-y-2">
                {["w1 masking", "w2 added level", "w3 unnaturalness"].map((lab, i) => (
                  <Slider key={lab} label={lab} min={0} max={3} step={0.05} value={w[i]} onChange={(v) => setW(w.map((x, j) => (j === i ? v : x)))} />
                ))}
              </div>
            )}
          </Panel>
          <Panel title="Limits">
            <div className="space-y-3">
              <label className="flex items-center gap-2 text-[13px]"><input type="checkbox" checked={cap !== null} onChange={(e) => setCap(e.target.checked ? 3 : null)} />Limit soundscape level relative to the machine</label>
              {cap !== null && <Slider label="Soundscape LA ≤ machine LA +" unit=" dB" min={-15} max={15} step={1} value={cap} onChange={setCap} />}
              <Field label="Max combined LA (optional)" hint={project.target.calibrated ? "dB(A) re 20 µPa" : "relative dB(A)"}><input className="input" value={maxMix} onChange={(e) => setMaxMix(e.target.value)} placeholder="none" /></Field>
              {mode === "expert" && <>
                <Slider label="Masking margin" unit=" dB" min={0} max={10} step={0.5} value={margin} onChange={setMargin} />
                <Slider label="K (S/M ratio at threshold)" unit=" dB" min={-8} max={0} step={0.5} value={k} onChange={setK} />
                <label className="flex items-center gap-2 text-[13px]"><input type="checkbox" checked={eq} onChange={(e) => setEq(e.target.checked)} />Allow gentle spectral shaping of broadband beds</label>
                <label className="flex items-center gap-2 text-[13px]"><input type="checkbox" checked={pareto} onChange={(e) => setPareto(e.target.checked)} />Explore the trade-off curve (Pareto, slower)</label>
              </>}
            </div>
          </Panel>
          <button className="btn btn-primary w-full justify-center" disabled={busy} onClick={run}>{busy ? "Optimising…" : "Run optimisation"}</button>
          <button className="btn w-full justify-center" disabled={!opt || !!gen} onClick={generate}>{project.render ? "Re-generate soundscape" : "Generate soundscape"}</button>
          {gen && <Progress value={gen.p} label={gen.msg} />}
        </div>
        <div className="min-w-0 space-y-5">
          {!opt ? <Empty title="No optimisation yet">Choose an objective and run the optimisation. It takes a few seconds.</Empty> : <OptView opt={opt} unit={unit} />}
          {ev && <EvalView ev={ev} view={view} setView={setView} />}
        </div>
      </div>
    </div>
  );
}

function OptView({ opt, unit }: { opt: OptResult; unit: string }) {
  const b = opt.bands;
  const data = useMemo(() => [
    { x: b.f_hz, y: b.L_target, name: "Machine (target)", type: "scatter", mode: "lines+markers", line: { color: C.target(), width: 2 }, marker: { size: 4 } },
    { x: b.f_hz, y: b.L_masker, name: "Soundscape (predicted)", type: "scatter", mode: "lines", line: { color: C.masker(), width: 2 } },
    { x: b.f_hz, y: b.threshold, name: "Estimated masked threshold", type: "scatter", mode: "lines", line: { color: C.threshold(), width: 1.5, dash: "dash" } },
  ], [opt]);
  // bar widths follow the local band spacing (Plotly sizes bars in linear Hz, which looks wrong on a log axis)
  const widths = b.f_hz.map((f, i) => 0.75 * ((b.f_hz[Math.min(i + 1, b.f_hz.length - 1)] - b.f_hz[Math.max(i - 1, 0)]) / (i === 0 || i === b.f_hz.length - 1 ? 1 : 2)));
  const marginData = useMemo(() => [{ x: b.f_hz, y: b.margin, width: widths, type: "bar", name: "margin",
    marker: { color: b.margin.map((m, i) => (b.weight[i] === 0 ? C.grid() : m > 0 ? C.bad() : m > -3 ? C.warn() : C.good())) },
    hovertemplate: "%{x:.0f} Hz: %{y:.1f} dB<extra></extra>" }], [opt]);
  return (
    <div className="space-y-5 rise">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <Stat label="Soundscape − machine" term="mtr" value={signed(opt.levels.masker_to_target_LA)} unit="dB(A)" tone="masker" />
        <Stat label="Total level change" term="deltaLA" value={signed(opt.levels.delta_LA)} unit="dB(A)" tone={opt.levels.delta_LA > 6 ? "bad" : opt.levels.delta_LA > 3 ? "warn" : "good"} />
        <Stat label="Prominence index" term="prominence" value={signed(opt.prominence_index_db)} unit="dB" tone={opt.prominence_index_db > 10 ? "bad" : opt.prominence_index_db > 0 ? "warn" : "good"} />
        <Stat label="Bands above goal" term="margin" value={`${opt.audible_band_count}/${opt.relevant_band_count}`} />
        <Stat label="Soundscape LA" value={fmt(opt.levels.LA_masker)} unit={unit} hint={`machine ${fmt(opt.levels.LA_target)} → mix ${fmt(opt.levels.LA_mix)}`} />
      </div>
      {opt.notes.map((n) => <Notice key={n}>{n}</Notice>)}
      <Panel title={<span>Predicted masking in <Term k="ERB">auditory (ERB) bands</Term></span>} right={<Badge>{opt.model.split("(")[0]}</Badge>}>
        <Plot data={data as any} height={320} layout={{ xaxis: logFreqAxis("Frequency (Hz)", [Math.log10(40), Math.log10(18000)]) as any, yaxis: { title: { text: `Filter-band level (${unit.replace("(A)", "")})` } } as any }} />
        <div className="mt-2 label">Margin per band (target − threshold): red = predicted audible, amber = within margin, green = masked</div>
        <Plot data={marginData as any} height={170} layout={{ showlegend: false, margin: { l: 56, r: 16, t: 6, b: 36 }, xaxis: logFreqAxis("", [Math.log10(40), Math.log10(18000)]) as any, yaxis: { title: { text: "dB" } } as any }} />
      </Panel>
      {opt.remaining_audible.length > 0 && (
        <Panel title="Still above the masking goal">
          <table className="num w-full text-[12.5px]"><thead><tr className="text-left text-muted"><th className="pb-1">Band</th><th>machine</th><th>soundscape</th><th>needed</th><th>shortfall</th></tr></thead>
            <tbody>{opt.remaining_audible.slice(0, 8).map((r) => (
              <tr key={r.band_hz} className="border-t border-line"><td className="py-1">{r.band_hz.toFixed(0)} Hz</td><td>{r.target_db.toFixed(1)}</td><td>{r.masker_db.toFixed(1)}</td><td>{r.required_masker_db.toFixed(1)}</td>
                <td style={{ color: r.shortfall_db > 6 ? "var(--bad)" : "var(--warn)" }}>{r.shortfall_db.toFixed(1)} dB</td></tr>))}</tbody></table>
        </Panel>
      )}
      {opt.pareto && (
        <Panel title="Trade-off: residual audibility vs added level">
          <Plot height={260} data={[
            { x: opt.pareto.points.map((p) => p.added_level), y: opt.pareto.points.map((p) => p.masking_loss), mode: "markers", type: "scatter", name: "solutions", marker: { color: C.muted(), size: 8 } },
            { x: opt.pareto.non_dominated.map((p) => p.added_level), y: opt.pareto.non_dominated.map((p) => p.masking_loss), mode: "lines+markers", type: "scatter", name: "non-dominated", line: { color: C.accent() }, marker: { size: 9 } },
            { x: [opt.terms.added_level_db], y: [opt.terms.masking_loss_db], mode: "markers", type: "scatter", name: "current", marker: { color: C.target(), size: 13, symbol: "diamond" } },
          ] as any} layout={{ xaxis: { title: { text: "Added A-weighted level (dB)" } } as any, yaxis: { title: { text: "Masking loss (dB RMS excess)" } } as any }} />
        </Panel>
      )}
      <div className="text-[12px] text-faint">Objective terms: masking loss {opt.terms.masking_loss_db.toFixed(2)} dB · added level {opt.terms.added_level_db.toFixed(2)} dB · unnaturalness {opt.terms.unnaturalness_db.toFixed(2)} dB · solver {opt.solver.success ? "converged" : opt.solver.message} ({opt.solver.iterations} it.)</div>
    </div>
  );
}

function EvalView({ ev, view, setView }: { ev: Evaluation; view: "erb" | "third" | "octave" | "psd"; setView: (v: any) => void }) {
  const data = useMemo(() => {
    if (view === "erb") return [
      { x: ev.erb.bands_hz, y: ev.erb.L_target, name: "Machine", type: "scatter", mode: "lines+markers", line: { color: C.target(), width: 2 }, marker: { size: 4 } },
      { x: ev.erb.bands_hz, y: ev.erb.L_masker, name: "Soundscape (rendered)", type: "scatter", mode: "lines", line: { color: C.masker(), width: 2 } },
      { x: ev.erb.bands_hz, y: ev.erb.threshold, name: "Estimated threshold", type: "scatter", mode: "lines", line: { color: C.threshold(), dash: "dash" } },
    ];
    if (view === "psd") return (["target", "masker", "mix"] as const).map((k) => ({ x: ev[k].psd.f, y: ev[k].psd.db, name: { target: "Machine", masker: "Soundscape", mix: "Combined" }[k],
      type: "scatter", mode: "lines", line: { color: { target: C.target(), masker: C.masker(), mix: C.mix() }[k], width: 1.2 } }));
    return (["target", "masker", "mix"] as const).map((k) => ({ x: ev[k][view].f, y: ev[k][view].L, name: { target: "Machine", masker: "Soundscape", mix: "Combined" }[k],
      type: "scatter", mode: "lines+markers", line: { color: { target: C.target(), masker: C.masker(), mix: C.mix() }[k], width: 2, shape: "hvh" }, marker: { size: 5 } }));
  }, [ev, view]);
  const u = ev.calibrated ? "dB" : "dB rel";
  return (
    <div className="space-y-5 rise">
      <div className="flex flex-wrap items-center gap-3"><h2 className="font-[family-name:var(--font-display)] text-[26px]">Evaluation of the rendered soundscape</h2><Badge tone="accent">computed from the actual audio</Badge></div>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <Stat label="Machine LAeq" value={fmt(ev.target.LAeq)} unit={u + "(A)"} tone="target" />
        <Stat label="Soundscape LAeq" value={fmt(ev.masker.LAeq)} unit={u + "(A)"} tone="masker" />
        <Stat label="Combined LAeq" value={fmt(ev.mix.LAeq)} unit={u + "(A)"} tone="mix" />
        <Stat label="Level change" term="deltaLA" value={signed(ev.delta_LA)} unit="dB(A)" />
        <Stat label="Prominence index" term="prominence" value={signed(ev.prominence_index_db)} unit="dB" hint={`${ev.audible_band_count} of ${ev.band_count} bands above goal`} />
      </div>
      {ev.interpretation.map((m) => <Notice key={m} tone="accent">{m}</Notice>)}
      <Panel title="Spectral comparison" right={<Tabs value={view} onChange={setView} items={[{ id: "erb", label: "ERB" }, { id: "third", label: "1/3 oct" }, { id: "octave", label: "1/1 oct" }, { id: "psd", label: "PSD" }]} />}>
        <Plot data={data as any} height={330} layout={{ xaxis: logFreqAxis() as any, yaxis: { title: { text: view === "psd" ? `${u}/Hz` : `Level (${u})` } } as any }} />
      </Panel>
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <Panel title={<Term k="mtr">Soundscape − machine per 1/3-octave band</Term>}>
          <Plot height={240} data={[{ x: ev.target.third.f, y: ev.masker_to_target_third, width: ev.target.third.f.map((f) => 0.18 * f), type: "bar", marker: { color: ev.masker_to_target_third.map((v) => (v >= 0 ? C.masker() : C.target())) },
            hovertemplate: "%{x:.0f} Hz: %{y:.1f} dB<extra></extra>" }] as any} layout={{ showlegend: false, xaxis: logFreqAxis() as any, yaxis: { title: { text: "dB" } } as any }} />
        </Panel>
        {ev.time_varying ? (
          <Panel title="Prominence over time (0.5 s frames)">
            <Plot height={240} data={[{ x: ev.time_varying.t, y: ev.time_varying.pi, type: "scatter", mode: "lines", line: { color: C.target(), width: 1.4 }, name: "prominence" }] as any}
              layout={{ showlegend: false, xaxis: { title: { text: "Time in recording (s)" } } as any, yaxis: { title: { text: "Prominence index (dB)" } } as any,
                shapes: [{ type: "line", x0: 0, x1: Math.max(...ev.time_varying.t), y0: 0, y1: 0, line: { color: C.threshold(), dash: "dot" } }] as any }} />
            <div className="text-[12px] text-muted">median {ev.time_varying.median.toFixed(1)} dB · 90th pct {ev.time_varying.p90.toFixed(1)} dB · max {ev.time_varying.max.toFixed(1)} dB</div>
          </Panel>
        ) : (
          <Panel title="Model assumptions"><ul className="list-disc space-y-1 pl-5 text-[12.5px] text-muted">{ev.assumptions.map((a) => <li key={a}>{a}</li>)}</ul></Panel>
        )}
      </div>
      {ev.time_varying && <Panel title="Model assumptions"><ul className="list-disc space-y-1 pl-5 text-[12.5px] text-muted">{ev.assumptions.map((a) => <li key={a}>{a}</li>)}</ul></Panel>}
    </div>
  );
}
