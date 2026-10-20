import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, waitJob, type ExportFile } from "../services/api";
import { useStudio } from "../hooks/useStudio";
import { Badge, Empty, Field, Notice, PageHeader, Panel, Progress } from "../components/ui";

const FORMATS = [
  { id: "wav16", label: "WAV 16-bit PCM" }, { id: "wav24", label: "WAV 24-bit PCM" }, { id: "wav32f", label: "WAV 32-bit float" },
  { id: "mat", label: "MATLAB .mat (sig, fs, t, levels, metadata)" }, { id: "csv", label: "CSV spectra (1/3, 1/1, PSD, ERB masking)" },
  { id: "json", label: "JSON project specification" }, { id: "report", label: "HTML engineering report" },
];

export default function ExportCenter() {
  const { project, toast } = useStudio();
  const nav = useNavigate();
  const [formats, setFormats] = useState<string[]>(["wav24", "mat", "report"]);
  const [stream, setStream] = useState("masker");
  const [channels, setChannels] = useState(2);
  const [domain, setDomain] = useState("digital");
  const [relative, setRelative] = useState(true);
  const [prog, setProg] = useState<{ p: number; msg: string } | null>(null);
  const [result, setResult] = useState<ExportFile[]>([]);
  const [files, setFiles] = useState<{ file: string; bytes: number }[]>([]);
  const load = () => project && api.listExports(project.id).then(setFiles).catch(() => setFiles([]));
  useEffect(() => { load(); }, [project?.id]);

  if (!project) return <Empty title="No project open">Create or open a project on the Dashboard first.</Empty>;
  if (!project.render) return <Empty title="Nothing to export yet">Generate a soundscape in the Masking Laboratory first.<div className="mt-4"><button className="btn" onClick={() => nav("/masking")}>Masking Laboratory</button></div></Empty>;
  const cal = !!project.target?.calibrated;

  async function run() {
    setProg({ p: 0, msg: "Starting" });
    try {
      const { job } = await api.exportFiles(project!.id, { formats, stream, channels, mat_signal_domain: domain, preserve_relative_level: relative });
      const r = await waitJob<{ files: ExportFile[] }>(job, (j) => setProg({ p: j.progress, msg: j.message }));
      setResult(r.files);
      await load();
      toast(`${r.files.length} file(s) written and validated`, "success");
    } catch (e: any) { toast(e.message, "error"); } finally { setProg(null); }
  }

  return (
    <div>
      <PageHeader step="Step 5" title="Export center" sub="Every export is re-read and validated after writing. MATLAB files open with load(); uncalibrated designs never receive SPL values." />
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[1fr_1fr]">
        <Panel title="What to export">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <Field label="Audio stream"><select className="input" value={stream} onChange={(e) => setStream(e.target.value)}>
              <option value="masker">Soundscape (for playback)</option><option value="mix">Machine + soundscape (for listening tests)</option><option value="target">Machine only</option></select></Field>
            <Field label="Channels"><select className="input" value={channels} onChange={(e) => setChannels(+e.target.value)}><option value={2}>Stereo</option><option value={1}>Mono (analysis)</option></select></Field>
            <Field label="MAT signal domain" hint={cal ? "Pa = pressure at the listener per the design" : "Pa requires a calibrated target"}>
              <select className="input" value={domain} onChange={(e) => setDomain(e.target.value)}>
                <option value="digital">Normalised digital samples</option><option value="pascal" disabled={!cal}>Pressure in Pascals</option></select></Field>
            <label className="mt-6 flex items-center gap-2 text-[13px]"><input type="checkbox" checked={relative} onChange={(e) => setRelative(e.target.checked)} />Keep levels relative to the machine (shared gain)</label>
          </div>
          <div className="mt-5 label">Formats</div>
          <div className="mt-2 grid grid-cols-1 gap-1.5 md:grid-cols-2">
            {FORMATS.map((f) => (
              <label key={f.id} className="flex items-center gap-2 text-[13px]"><input type="checkbox" checked={formats.includes(f.id)}
                onChange={(e) => setFormats(e.target.checked ? [...formats, f.id] : formats.filter((x) => x !== f.id))} />{f.label}</label>
            ))}
          </div>
          <div className="mt-5 flex items-center gap-3">
            <button className="btn btn-primary" disabled={!formats.length || !!prog} onClick={run}>Export</button>
            <span className="text-[12px] text-faint">{project.render.duration_s.toFixed(0)} s · {project.render.fs / 1000} kHz · seed {project.render.seed}</span>
          </div>
          {prog && <div className="mt-3"><Progress value={prog.p} label={prog.msg} /></div>}
          {!cal && <div className="mt-4"><Notice>This design is uncalibrated: the MAT file will contain relative levels <span className="num">Lrel_*</span> (dB re full scale) and no SPL values.</Notice></div>}
        </Panel>
        <Panel title="Files" right={<span className="text-[12px] text-faint">stored in the project folder</span>}>
          {result.length > 0 && (
            <div className="mb-4 space-y-1.5">
              <div className="label">Last export — validation</div>
              {result.map((r) => (
                <div key={r.file} className="flex flex-wrap items-center gap-2 text-[12.5px]">
                  {r.valid ? <Badge tone="good">valid</Badge> : <Badge tone="bad">check failed</Badge>}
                  <span className="num truncate">{r.file}</span>
                  {"subtype" in r && <span className="text-faint">{String(r.subtype)} · {String(r.samplerate)} Hz · {String(r.channels)} ch</span>}
                  {r.format === "mat" && <span className="text-faint">{String(r.signal_domain)} · {String(r.precision)}</span>}
                </div>
              ))}
            </div>
          )}
          {files.length === 0 ? <p className="text-muted">No exports yet.</p> : (
            <ul className="divide-y divide-[var(--line)]">
              {files.map((f) => (
                <li key={f.file} className="flex items-center gap-3 py-2">
                  <span className="num min-w-0 flex-1 truncate text-[12.5px]">{f.file}</span>
                  <span className="text-[12px] text-faint">{(f.bytes / 1e6).toFixed(2)} MB</span>
                  <a className="btn !py-1 text-[12px]" href={api.exportUrl(project.id, f.file)} download>Download</a>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>
    </div>
  );
}
