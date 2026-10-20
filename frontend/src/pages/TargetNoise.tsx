import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type Analysis } from "../services/api";
import { fmt, useStudio } from "../hooks/useStudio";
import { Badge, DomainBadge, Empty, Field, FileDrop, Notice, PageHeader, Panel, Stat, Tabs, Term } from "../components/ui";
import { BANDS, SpectrumEditor, convert, type EditorValue, type Rep } from "../components/SpectrumEditor";
import { C, Plot, logFreqAxis } from "../charts/Plot";

type Mode = "upload" | "editor" | "manual" | "demo";

export default function TargetNoise() {
  const { project, analysis, setAnalysis, refresh, toast, catalog, mode: uiMode } = useStudio();
  const nav = useNavigate();
  const [mode, setMode] = useState<Mode>("upload");
  if (!project) return <Empty title="No project open">Create or open a project on the Dashboard first.</Empty>;

  const applied = async (r: { analysis: Analysis; warnings?: string[] }) => {
    setAnalysis(r.analysis);
    await refresh();
    (r.warnings || []).forEach((w) => toast(w));
    toast("Target updated", "success");
  };

  return (
    <div>
      <PageHeader step="Step 1" title="Target noise" sub="Define the machine or tool you want to make less noticeable. Every input is labelled as measured, estimated or synthetic."
        right={analysis && <button className="btn btn-primary" onClick={() => nav("/soundscape")}>Next: environment →</button>} />
      <div className="mb-4"><Tabs value={mode} onChange={setMode} items={[
        { id: "upload", label: "Import file" }, { id: "editor", label: "Spectrum / Lw editor" },
        { id: "manual", label: "Manual values" }, { id: "demo", label: "Demo machines" }]} /></div>
      <div className="mb-8">
        {mode === "upload" && <UploadMode pid={project.id} onApplied={applied} />}
        {mode === "editor" && <EditorMode pid={project.id} onApplied={applied} expert={uiMode === "expert"} />}
        {mode === "manual" && <ManualMode pid={project.id} onApplied={applied} templates={catalog?.machine_templates || {}} />}
        {mode === "demo" && <DemoMode pid={project.id} onApplied={applied} demos={catalog?.demo_targets || {}} />}
      </div>
      {analysis ? <AnalysisView a={analysis} name={project.target?.name || ""} notes={project.target?.meta?.notes || []} /> :
        <Empty title="No target analysed yet">Import a recording or spectrum, enter values, or pick a demo machine.</Empty>}
    </div>
  );
}

/* ------------------------------------------------------------------ upload */

function UploadMode({ pid, onApplied }: { pid: string; onApplied: (r: any) => Promise<void> }) {
  const { toast } = useStudio();
  const [busy, setBusy] = useState(false);
  const [info, setInfo] = useState<any>(null);
  const [domain, setDomain] = useState("DIGITAL_UNCALIBRATED");
  const [k, setK] = useState("");
  const [refLa, setRefLa] = useState("");
  const [calMethod, setCalMethod] = useState<"factor" | "reference">("factor");
  const [channel, setChannel] = useState<string>("0");
  const [fs, setFs] = useState("");
  const [map, setMap] = useState<any>({});

  async function onFile(f: File) {
    setBusy(true);
    setInfo(null);
    try {
      const r = await api.upload(pid, f);
      setInfo(r);
      if (r.kind === "signal") {
        setDomain(r.suggested_domain.domain);
        if (r.suggested_domain.k_pa_per_unit) setK(String(r.suggested_domain.k_pa_per_unit));
        setFs(r.fs ? String(r.fs) : "");
      } else {
        setMap({ frequency_column: r.suggested.frequency_column, level_column: r.suggested.level_columns[0], representation: r.suggested.representation,
          quantity: r.suggested.quantity, a_weighted: r.suggested.a_weighted, distance_m: "", measured_at_m: "", field: "hemispherical", pattern: "stationary" });
      }
    } catch (e: any) {
      toast(e.message, "error");
    } finally {
      setBusy(false);
    }
  }

  async function applySignal() {
    setBusy(true);
    try {
      const body: any = { domain, channel: channel === "mean" ? "mean" : parseInt(channel), name: info.file, fs: fs ? parseFloat(fs) : null };
      if (domain === "DIGITAL_CALIBRATED") {
        if (calMethod === "factor") body.k_pa_per_unit = parseFloat(k);
        else body.reference_la = parseFloat(refLa);
      }
      await onApplied(await api.configureSignal(pid, body));
    } catch (e: any) { toast(e.message, "error"); } finally { setBusy(false); }
  }

  async function applyTable() {
    setBusy(true);
    try {
      await onApplied(await api.configureTable(pid, { ...map, name: info.file, distance_m: map.distance_m ? parseFloat(map.distance_m) : null,
        measured_at_m: map.measured_at_m ? parseFloat(map.measured_at_m) : null }));
    } catch (e: any) { toast(e.message, "error"); } finally { setBusy(false); }
  }

  return (
    <div className="grid grid-cols-1 gap-5 lg:grid-cols-[1fr_1.4fr]">
      <FileDrop accept=".mat,.wav,.flac,.ogg,.csv,.txt,.xlsx,.xls" onFile={onFile} busy={busy}
        label="MATLAB .mat (sig, fs, t, dist, line), WAV/FLAC, or a CSV/Excel spectrum table" />
      {!info && <Panel title="Supported inputs"><ul className="space-y-1.5 text-[13px] text-muted">
        <li><b className="text-text">.mat</b> v4–v7 and v7.3 (HDF5). Variables <span className="num">sig</span> (N×C), <span className="num">fs</span>, optional <span className="num">t, dist, line</span>, calibration.</li>
        <li><b className="text-text">.wav / .flac</b> digital recordings (uncalibrated unless you add calibration).</li>
        <li><b className="text-text">.csv / .xlsx / .xls</b> frequency + level columns: octave, third-octave or narrowband; Lp or Lw; dB or dBA.</li>
      </ul></Panel>}
      {info?.kind === "signal" && (
        <Panel title={`Recording: ${info.file}`} right={<Badge>{info.format}</Badge>}>
          <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat label="Channels" value={String(info.channels)} />
            <Stat label="Sample rate" value={info.fs ? fmt(info.fs, 0) : "unknown"} unit={info.fs ? "Hz" : ""} />
            <Stat label="Duration" value={info.duration_s ? fmt(info.duration_s, 2) : "—"} unit="s" />
            <Stat label="Peak |sig|" value={info.peak.toPrecision(3)} />
          </div>
          {info.meta && Object.keys(info.meta).length > 0 && <div className="mb-3 text-[12px] text-muted">Metadata found: <span className="num">{JSON.stringify(info.meta).slice(0, 220)}</span></div>}
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <Field label="Signal domain" term="calibration" hint={info.suggested_domain.reason}>
              <select className="input" value={domain} onChange={(e) => setDomain(e.target.value)}>
                <option value="PASCAL">Sound pressure in Pascals (calibrated)</option>
                <option value="DIGITAL_CALIBRATED">Digital samples + calibration</option>
                <option value="DIGITAL_UNCALIBRATED">Digital samples, uncalibrated (relative dB only)</option>
              </select>
            </Field>
            <Field label="Channel">
              <select className="input" value={channel} onChange={(e) => setChannel(e.target.value)}>
                {Array.from({ length: info.channels }).map((_, i) => <option key={i} value={i}>Channel {i + 1} (rms {info.channel_rms[i].toPrecision(3)})</option>)}
                {info.channels > 1 && <option value="mean">Mean of all channels</option>}
              </select>
            </Field>
            {!info.fs && <Field label="Sample rate (Hz)" hint="Not found in the file — required."><input className="input" value={fs} onChange={(e) => setFs(e.target.value)} /></Field>}
            {domain === "DIGITAL_CALIBRATED" && (
              <>
                <Field label="Calibration method">
                  <select className="input" value={calMethod} onChange={(e) => setCalMethod(e.target.value as any)}>
                    <option value="factor">Factor k (Pa per digital unit)</option>
                    <option value="reference">Known LAeq of this recording (reference level)</option>
                  </select>
                </Field>
                {calMethod === "factor" ? <Field label="k (Pa per unit)" hint="E.g. 1 / rms of a 94 dB (1 Pa) calibrator recording."><input className="input" value={k} onChange={(e) => setK(e.target.value)} /></Field>
                  : <Field label="Reference LAeq (dB)" hint="Measured with a sound level meter at the same position."><input className="input" value={refLa} onChange={(e) => setRefLa(e.target.value)} /></Field>}
              </>
            )}
          </div>
          {info.suggested_domain.needs_confirmation && <div className="mt-3"><Notice>Please confirm the domain: values above 1 can be pressure in Pa, but could also be unnormalised digital data.</Notice></div>}
          <div className="mt-4 flex justify-end"><button className="btn btn-primary" disabled={busy} onClick={applySignal}>Analyse recording</button></div>
        </Panel>
      )}
      {info?.kind === "table" && (
        <Panel title={`Table: ${info.file}`} right={<Badge>{info.row_count} rows</Badge>}>
          <div className="mb-3 max-h-40 overflow-auto rounded border border-line">
            <table className="num w-full text-[12px]"><thead><tr>{info.columns.map((c: string) => <th key={c} className="border-b border-line px-2 py-1 text-left text-muted">{c}</th>)}</tr></thead>
              <tbody>{info.preview.slice(0, 12).map((r: any[], i: number) => <tr key={i}>{r.map((v, j) => <td key={j} className="px-2 py-0.5">{v ?? "—"}</td>)}</tr>)}</tbody></table>
          </div>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            <Field label="Frequency column"><select className="input" value={map.frequency_column} onChange={(e) => setMap({ ...map, frequency_column: e.target.value })}>{info.columns.map((c: string) => <option key={c}>{c}</option>)}</select></Field>
            <Field label="Level column"><select className="input" value={map.level_column} onChange={(e) => setMap({ ...map, level_column: e.target.value })}>{info.columns.map((c: string) => <option key={c}>{c}</option>)}</select></Field>
            <Field label="Representation" hint="Detected automatically; change if wrong."><select className="input" value={map.representation} onChange={(e) => setMap({ ...map, representation: e.target.value })}>
              <option value="octave">Octave-band levels</option><option value="third">1/3-octave-band levels</option><option value="continuous">Narrowband spectrum level (dB/Hz)</option></select></Field>
            <Field label="Quantity" term="Lw"><select className="input" value={map.quantity} onChange={(e) => setMap({ ...map, quantity: e.target.value })}>
              <option value="Lp">Sound pressure level Lp</option><option value="Lw">Sound power level Lw</option></select></Field>
            <Field label={map.quantity === "Lw" ? "Listener distance (m)" : "Listener distance (m, optional)"} hint={map.quantity === "Lw" ? "Required to convert Lw to Lp." : "With a measurement distance: free-field correction."}>
              <input className="input" value={map.distance_m} onChange={(e) => setMap({ ...map, distance_m: e.target.value })} /></Field>
            {map.quantity === "Lw" ? <Field label="Radiation"><select className="input" value={map.field} onChange={(e) => setMap({ ...map, field: e.target.value })}>
              <option value="hemispherical">Source on the ground (hemispherical)</option><option value="free">Free field (spherical)</option></select></Field>
              : <Field label="Measured at (m, optional)"><input className="input" value={map.measured_at_m} onChange={(e) => setMap({ ...map, measured_at_m: e.target.value })} /></Field>}
          </div>
          <label className="mt-3 flex items-center gap-2 text-[13px]"><input type="checkbox" checked={map.a_weighted} onChange={(e) => setMap({ ...map, a_weighted: e.target.checked })} />Levels are A-weighted band levels (dBA) — remove A-weighting</label>
          <div className="mt-4 flex justify-end"><button className="btn btn-primary" disabled={busy} onClick={applyTable}>Use this spectrum</button></div>
        </Panel>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ editor */

const DEFAULT_OCT: EditorValue = { rep: "octave", f: BANDS.octave, L: [62, 68, 72, 75, 78, 80, 77, 72, 65, 55] };

function EditorMode({ pid, onApplied, expert }: { pid: string; onApplied: (r: any) => Promise<void>; expert: boolean }) {
  const { toast } = useStudio();
  const [v, setV] = useState<EditorValue>(DEFAULT_OCT);
  const [quantity, setQuantity] = useState<"Lp" | "Lw">("Lp");
  const [dist, setDist] = useState("5");
  const [measured, setMeasured] = useState("");
  const [field, setField] = useState("hemispherical");
  const [di, setDi] = useState("0");
  const [air, setAir] = useState(false);
  const [unc, setUnc] = useState(0);
  const [tones, setTones] = useState<{ f: number; level_db: number }[]>([]);
  const [pattern, setPattern] = useState("stationary");
  const [paste, setPaste] = useState("");
  const [busy, setBusy] = useState(false);

  const switchRep = (r: Rep) => setV(convert(v, r));
  const importPairs = () => {
    const rows = paste.split(/\r?\n/).map((l) => l.trim().split(/[\s,;\t]+/).map(Number)).filter((r) => r.length >= 2 && r.every(Number.isFinite) && r[0] > 0);
    if (rows.length < 2) { toast("Paste at least two lines of 'frequency, level'", "error"); return; }
    rows.sort((a, b) => a[0] - b[0]);
    const f = rows.map((r) => r[0]), L = rows.map((r) => r[1]);
    const isOct = f.every((x) => BANDS.octave.some((o) => Math.abs(Math.log(o / x)) < 0.03));
    const isThird = f.every((x) => BANDS.third.some((o) => Math.abs(Math.log(o / x)) < 0.03));
    setV({ rep: isOct && f.length <= 10 ? "octave" : isThird ? "third" : "continuous", f, L });
    toast(`Imported ${rows.length} points`);
  };

  async function apply() {
    setBusy(true);
    try {
      await onApplied(await api.setSpectrum(pid, { f: v.f, L: v.L, representation: v.rep, quantity, distance_m: dist ? parseFloat(dist) : null,
        measured_at_m: measured ? parseFloat(measured) : null, field, directivity_db: parseFloat(di) || 0, air_absorption: air, tones, pattern,
        uncertainty_db: unc || null, name: quantity === "Lw" ? "Sound power spectrum (Lw)" : "Edited spectrum" }));
    } catch (e: any) { toast(e.message, "error"); } finally { setBusy(false); }
  }

  const unit = v.rep === "continuous" ? `${quantity === "Lw" ? "dB re 1 pW" : "dB re (20 µPa)²"}/Hz` : quantity === "Lw" ? "dB re 1 pW per band" : "dB re 20 µPa per band";
  return (
    <div className="grid grid-cols-1 gap-5 xl:grid-cols-[1fr_320px]">
      <Panel title="Spectral editor" right={<Tabs value={v.rep} onChange={switchRep} items={[{ id: "octave", label: "1/1 octave" }, { id: "third", label: "1/3 octave" }, { id: "continuous", label: "Continuous" }]} />}>
        <SpectrumEditor value={v} onChange={setV} unit={unit} uncertainty={unc} tones={tones} onTones={setTones} />
        <p className="mt-2 text-[12px] text-faint">Switching representation converts physically: band levels ↔ spectrum level (dB/Hz) via bandwidth; 1/3→1/1 by energy sum. Octave→third subdivision is an estimate.</p>
      </Panel>
      <div className="space-y-4">
        <Panel title="What the values mean">
          <div className="space-y-3">
            <Field label="Quantity" term="Lw"><select className="input" value={quantity} onChange={(e) => setQuantity(e.target.value as any)}>
              <option value="Lp">Sound pressure level Lp (at a position)</option><option value="Lw">Sound power level Lw (of the machine)</option></select></Field>
            <Field label="Listener distance (m)" hint={quantity === "Lw" ? "Lp = Lw + DI − 10·log10(Ω r²)" : "Optional, with 'measured at' for a distance correction"}>
              <input className="input" value={dist} onChange={(e) => setDist(e.target.value)} /></Field>
            {quantity === "Lp" && <Field label="Measured at (m, optional)"><input className="input" value={measured} onChange={(e) => setMeasured(e.target.value)} /></Field>}
            {quantity === "Lw" && <>
              <Field label="Radiation"><select className="input" value={field} onChange={(e) => setField(e.target.value)}>
                <option value="hemispherical">Source on the ground (2π)</option><option value="free">Free field (4π)</option></select></Field>
              {expert && <Field label="Directivity index (dB)"><input className="input" value={di} onChange={(e) => setDi(e.target.value)} /></Field>}
              {expert && <label className="flex items-center gap-2 text-[13px]"><input type="checkbox" checked={air} onChange={(e) => setAir(e.target.checked)} />ISO 9613-1 air absorption</label>}
            </>}
            <Field label="Operating pattern"><select className="input" value={pattern} onChange={(e) => setPattern(e.target.value)}>
              <option value="stationary">Stationary</option><option value="intermittent">Intermittent (on/off)</option><option value="varying">Time-varying</option></select></Field>
            <Field label={`Uncertainty band ±${unc} dB`}><input type="range" min={0} max={6} step={0.5} value={unc} onChange={(e) => setUnc(+e.target.value)} /></Field>
          </div>
        </Panel>
        <Panel title="Paste frequency / level pairs">
          <textarea className="input h-24" placeholder={"63, 70\n125, 72\n250, 75"} value={paste} onChange={(e) => setPaste(e.target.value)} aria-label="Frequency level pairs" />
          <button className="btn mt-2 w-full justify-center" onClick={importPairs}>Import pairs</button>
        </Panel>
        <button className="btn btn-primary w-full justify-center" disabled={busy} onClick={apply}>Use this spectrum</button>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ manual */

function ManualMode({ pid, onApplied, templates }: { pid: string; onApplied: (r: any) => Promise<void>; templates: Record<string, string> }) {
  const { toast } = useStudio();
  const [f, setF] = useState<any>({ la: "78", lz: "", lc: "", template: "electric_drill", distance_m: "1", listener_m: "", operating_mode: "", uncertainty_db: "", pattern: "intermittent" });
  const [busy, setBusy] = useState(false);
  const num = (s: string) => (s === "" ? null : parseFloat(s));
  async function apply() {
    setBusy(true);
    try {
      await onApplied(await api.setManual(pid, { ...f, la: num(f.la), lz: num(f.lz), lc: num(f.lc), distance_m: num(f.distance_m), listener_m: num(f.listener_m), uncertainty_db: num(f.uncertainty_db) }));
    } catch (e: any) { toast(e.message, "error"); } finally { setBusy(false); }
  }
  return (
    <Panel title="Manual acoustic values">
      <Notice tone="accent">An overall dBA value does not define a unique spectrum. The app shapes the spectrum with a machine template and labels the result <b>ESTIMATED</b>. Enter band levels in the editor if you have them.</Notice>
      <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-4">
        <Field label="LA (dBA) *" term="LAeq"><input className="input" value={f.la} onChange={(e) => setF({ ...f, la: e.target.value })} /></Field>
        <Field label="LZ (dB, optional)" term="LZeq"><input className="input" value={f.lz} onChange={(e) => setF({ ...f, lz: e.target.value })} /></Field>
        <Field label="LC (dB, optional)" term="LCeq" hint="Used to check the template's low-frequency content"><input className="input" value={f.lc} onChange={(e) => setF({ ...f, lc: e.target.value })} /></Field>
        <Field label="Spectral template"><select className="input" value={f.template} onChange={(e) => setF({ ...f, template: e.target.value })}>
          {Object.entries(templates).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></Field>
        <Field label="Measured at (m)"><input className="input" value={f.distance_m} onChange={(e) => setF({ ...f, distance_m: e.target.value })} /></Field>
        <Field label="Listener at (m, optional)" hint="Free-field distance correction"><input className="input" value={f.listener_m} onChange={(e) => setF({ ...f, listener_m: e.target.value })} /></Field>
        <Field label="Operating mode"><input className="input !font-sans" placeholder="e.g. drilling concrete" value={f.operating_mode} onChange={(e) => setF({ ...f, operating_mode: e.target.value })} /></Field>
        <Field label="Uncertainty (± dB)"><input className="input" value={f.uncertainty_db} onChange={(e) => setF({ ...f, uncertainty_db: e.target.value })} /></Field>
        <Field label="Temporal pattern"><select className="input" value={f.pattern} onChange={(e) => setF({ ...f, pattern: e.target.value })}>
          <option value="stationary">Stationary</option><option value="intermittent">Intermittent</option><option value="varying">Time-varying</option></select></Field>
      </div>
      <div className="mt-4 flex justify-end"><button className="btn btn-primary" disabled={busy} onClick={apply}>Build estimated spectrum</button></div>
    </Panel>
  );
}

function DemoMode({ pid, onApplied, demos }: { pid: string; onApplied: (r: any) => Promise<void>; demos: Record<string, string> }) {
  const { toast } = useStudio();
  const blurbs: Record<string, string> = {
    drill: "Broadband 1–4 kHz + whine at 2.4 kHz, hum at 120 Hz, intermittent.",
    grinder_hf: "Energy concentrated 4–10 kHz with a 6.3 kHz tone.",
    generator_lf: "50/100/150 Hz harmonics — the hard case for natural masking.",
    fan: "Low-mid broadband with a 240 Hz blade tone.",
  };
  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
      {Object.entries(demos).map(([k, label]) => (
        <button key={k} className="panel p-4 text-left hover:border-[var(--accent)]"
          onClick={() => api.setDemo(pid, k).then(onApplied).catch((e) => toast(e.message, "error"))}>
          <div className="font-semibold">{label}</div>
          <div className="mt-1 text-[12.5px] text-muted">{blurbs[k]}</div>
          <div className="mt-3"><Badge tone="warn">synthetic · not a measurement</Badge></div>
        </button>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ analysis */

function AnalysisView({ a, name, notes }: { a: Analysis; name: string; notes: string[] }) {
  const [specView, setSpecView] = useState<"third" | "octave" | "psd">("third");
  const u = a.calibrated ? "dB" : "dB rel";
  const spec = useMemo(() => {
    if (specView === "psd") return [{ x: a.psd.f, y: a.psd.db, type: "scatter", mode: "lines", name: "PSD", line: { color: C.target(), width: 1.3 } }];
    const s = a[specView];
    return [
      { x: s.f, y: s.L, width: s.f.map((f) => f * (specView === "octave" ? 0.55 : 0.18)), type: "bar", name: "Z (unweighted)", marker: { color: C.target() }, opacity: 0.85, hovertemplate: "%{x:.0f} Hz: %{y:.1f} dB<extra>Z</extra>" },
      { x: s.f, y: s.LA, type: "scatter", mode: "lines+markers", name: "A-weighted", line: { color: C.mix(), width: 1.5 }, marker: { size: 4 }, hovertemplate: "%{x:.0f} Hz: %{y:.1f} dB(A)<extra></extra>" },
    ];
  }, [a, specView]);
  const prominentTones = a.tones.filter((t) => t.prominent);
  return (
    <div className="space-y-5 rise">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="font-[family-name:var(--font-display)] text-[26px]">Analysis · {name}</h2>
        <DomainBadge domain={a.domain} provenance={a.provenance} />
      </div>
      {a.synthetic_note && <Notice tone="accent">{a.synthetic_note}. Audio previews of this target are reconstructed from the spectrum.</Notice>}
      {notes.length > 0 && <Notice>{notes.join(" ")}</Notice>}
      {!a.calibrated && <Notice>Uncalibrated recording: all levels are relative (dB re full scale). Calibrate on import to obtain dB SPL.</Notice>}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
        <Stat label="LAeq" term="LAeq" value={fmt(a.levels.LAeq)} unit={a.calibrated ? "dB(A)" : "dB(A) rel"} tone="target" />
        <Stat label="LZeq" term="LZeq" value={fmt(a.levels.LZeq)} unit={u} />
        <Stat label="LCeq" term="LCeq" value={fmt(a.levels.LCeq)} unit={u} hint={a.levels.LCeq != null && a.levels.LAeq != null ? `LC − LA = ${(a.levels.LCeq - a.levels.LAeq).toFixed(1)} dB` : undefined} />
        {a.levels.LAFmax != null && <Stat label="LAFmax" term="LAFmax" value={fmt(a.levels.LAFmax)} unit={u} />}
        {a.levels.LA10 != null && <Stat label="LA10" term="L10" value={fmt(a.levels.LA10)} unit={u} />}
        {a.levels.LA90 != null && <Stat label="LA90" term="L90" value={fmt(a.levels.LA90)} unit={u} />}
        <Stat label="Masking difficulty" term="difficulty" value={a.difficulty.level} tone={a.difficulty.level === "high" ? "bad" : a.difficulty.level === "medium" ? "warn" : "good"} />
      </div>
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[1.6fr_1fr]">
        <Panel title={<span>Spectrum · <Term k={specView === "psd" ? "PSD" : specView}>{specView === "psd" ? "power spectral density" : specView === "third" ? "1/3-octave bands" : "octave bands"}</Term></span>}
          right={<Tabs value={specView} onChange={setSpecView} items={[{ id: "third", label: "1/3 oct" }, { id: "octave", label: "1/1 oct" }, { id: "psd", label: "PSD" }]} />}>
          <Plot data={spec as any} height={330} layout={{ barmode: "overlay", bargap: 0.15, xaxis: logFreqAxis() as any,
            yaxis: { title: { text: specView === "psd" ? a.psd.unit : `Level (${a.level_unit})` } } as any }} />
        </Panel>
        <Panel title="Character">
          <div className="space-y-4 text-[13px]">
            <div>
              <div className="label mb-1">Temporal behaviour</div>
              <div className="flex items-center gap-2"><Badge tone="accent">{a.temporal.class}</Badge>
                {typeof a.temporal.L10_minus_L90_db === "number" && <span className="text-muted">L10 − L90 = <span className="num">{(a.temporal.L10_minus_L90_db as number).toFixed(1)}</span> dB</span>}</div>
            </div>
            <div>
              <div className="label mb-1">Dominant bands (A-weighted)</div>
              <div className="flex flex-wrap gap-1.5">{a.dominant_bands.map((b) => <Badge key={b} tone="target">{b} Hz</Badge>)}</div>
            </div>
            <div>
              <div className="label mb-1"><Term k="difficulty">Why masking may be hard</Term></div>
              <ul className="list-disc space-y-1 pl-5 text-muted">{a.difficulty.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
            </div>
            <div>
              <div className="label mb-1"><Term k="tonal">Tonal components</Term></div>
              {a.tones.length === 0 ? <div className="text-muted">None detected.</div> : (
                <table className="num w-full text-[12px]"><thead><tr className="text-left text-muted"><th>f (Hz)</th><th>level</th><th>TNR</th><th>crit.</th><th></th></tr></thead>
                  <tbody>{a.tones.slice(0, 8).map((t, i) => (
                    <tr key={i} className="border-t border-line"><td className="py-1">{t.frequency_hz.toFixed(0)}</td><td>{t.level_db.toFixed(1)}</td>
                      <td>{t.tnr_db != null ? t.tnr_db.toFixed(1) : t.declared ? "declared" : "—"}</td><td>{t.tnr_criterion_db != null ? t.tnr_criterion_db.toFixed(1) : ""}</td>
                      <td>{t.prominent ? <Badge tone="bad">prominent</Badge> : <Badge>minor</Badge>}</td></tr>))}</tbody></table>)}
              {prominentTones.length > 0 && <p className="mt-2 text-[12px] text-faint">Prominent tones need masker energy inside the same auditory band; they are the hardest part to hide.</p>}
            </div>
          </div>
        </Panel>
      </div>
      {a.waveform && (
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
          <Panel title="Waveform">
            <Plot height={220} data={[
              { x: [...a.waveform.t, ...[...a.waveform.t].reverse()], y: [...a.waveform.max, ...[...a.waveform.min].reverse()], type: "scatter", fill: "toself", mode: "lines",
                line: { color: C.target(), width: 0.6 }, fillcolor: C.target(), opacity: 0.6, hoverinfo: "skip", name: "envelope" } as any]}
              layout={{ showlegend: false, xaxis: { title: { text: "Time (s)" } } as any, yaxis: { title: { text: a.waveform.unit } } as any }} />
          </Panel>
          {a.level_history && <Panel title="A-weighted level history (Fast)">
            <Plot height={220} data={[{ x: a.level_history.t, y: a.level_history.LAF, type: "scatter", mode: "lines", line: { color: C.target(), width: 1.2 }, name: "LAF" }]}
              layout={{ showlegend: false, xaxis: { title: { text: "Time (s)" } } as any, yaxis: { title: { text: a.calibrated ? "dB(A)" : "dB(A) rel" } } as any }} />
          </Panel>}
        </div>
      )}
      {a.spectrogram && (
        <Panel title="Spectrogram">
          <Plot height={300} data={[{ z: a.spectrogram.db[0] ? transpose(a.spectrogram.db) : [], x: a.spectrogram.t, y: a.spectrogram.f, type: "heatmap",
            colorscale: [[0, "#0d1210"], [0.35, "#1f3b33"], [0.6, "#6b5a2a"], [0.82, "#e8a04b"], [1, "#fff1cf"]],
            colorbar: { title: { text: "dB/Hz" }, tickfont: { color: C.muted() } } } as any]}
            layout={{ yaxis: { type: "log", title: { text: "Frequency (Hz)" }, range: [Math.log10(30), Math.log10(16000)] } as any, xaxis: { title: { text: "Time (s)" } } as any }} />
        </Panel>
      )}
    </div>
  );
}

function transpose(m: number[][]): number[][] {
  return m[0].map((_, j) => m.map((row) => row[j]));
}
