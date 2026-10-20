import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type ProjectSummary } from "../services/api";
import { useStudio } from "../hooks/useStudio";
import { Badge, Notice, Panel } from "../components/ui";

const FLOW = [
  { n: "1", t: "Target noise", d: "Import a recording, a spectrum table, Lw data, or type values.", to: "/target" },
  { n: "2", t: "Environment", d: "Pick a natural setting and tune its sound sources.", to: "/soundscape" },
  { n: "3", t: "Masking", d: "Optimise levels against the machine's spectrum under level limits.", to: "/masking" },
  { n: "4", t: "Listen", d: "Compare machine, soundscape and mix — sample-aligned, blind A/B.", to: "/studio" },
  { n: "5", t: "Export", d: "WAV, MATLAB .mat, spectra and a technical report.", to: "/export" },
];

export default function Dashboard() {
  const { project, openProject, toast } = useStudio();
  const nav = useNavigate();
  const [list, setList] = useState<ProjectSummary[]>([]);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);

  const load = () => api.projects().then(setList).catch((e) => toast(e.message, "error"));
  useEffect(() => { load(); }, []);

  async function create(n?: string) {
    setBusy(true);
    try {
      const p = await api.createProject(n || name || "Untitled project");
      await openProject(p.id);
      setName("");
      await load();
      return p;
    } catch (e: any) {
      toast(e.message, "error");
    } finally {
      setBusy(false);
    }
  }

  async function quickDemo() {
    setBusy(true);
    try {
      const p = await api.createProject("Demo — drill in the countryside");
      await api.setDemo(p.id, "drill");
      await api.setScene(p.id, { preset: "countryside_afternoon" });
      await openProject(p.id);
      await load();
      toast("Demo project created with a synthetic drill target. Next: run the masking optimisation.", "success");
      nav("/masking");
    } catch (e: any) {
      toast(e.message, "error");
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    try {
      await api.deleteProject(id);
      await load();
      toast("Project deleted");
    } catch (e: any) { toast(e.message, "error"); }
  }

  return (
    <div className="space-y-6">
      <section className="relative overflow-hidden rounded-2xl border border-line bg-panel px-8 py-9">
        <svg className="pointer-events-none absolute -right-10 top-0 h-full w-[60%] opacity-[.22]" viewBox="0 0 600 220" preserveAspectRatio="none" aria-hidden>
          {Array.from({ length: 14 }).map((_, i) => (
            <path key={i} d={`M0 ${110 + Math.sin(i) * 20} C 150 ${40 + i * 9}, 300 ${190 - i * 7}, 600 ${100 + i * 3}`} fill="none"
              stroke={i % 4 === 0 ? "var(--target)" : "var(--accent)"} strokeWidth={i % 4 === 0 ? 1.4 : 0.9} />
          ))}
        </svg>
        <div className="relative max-w-2xl">
          <div className="label mb-2">Acoustic masking · generative soundscapes</div>
          <h1 className="font-[family-name:var(--font-display)] text-[46px] leading-[1.05]">Make the machine recede into the landscape.</h1>
          <p className="mt-3 text-[15px] text-muted">
            NatureMask Studio analyses a tool's acoustic signature and composes a natural soundscape whose energy sits where the machine is audible —
            while keeping the added sound level under control.
          </p>
          <div className="mt-6 flex flex-wrap items-center gap-3">
            <input className="input !w-64 !font-sans" placeholder="New project name" value={name} onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") create().then((p) => p && nav("/target")); }} aria-label="New project name" />
            <button className="btn btn-primary" disabled={busy} onClick={() => create().then((p) => p && nav("/target"))}>Create project</button>
            <button className="btn" disabled={busy} onClick={quickDemo}>Try the drill demo</button>
          </div>
        </div>
      </section>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-5">
        {FLOW.map((f) => (
          <button key={f.n} onClick={() => nav(f.to)} disabled={!project}
            className="panel group p-4 text-left transition-colors hover:border-[var(--accent)] disabled:opacity-60">
            <div className="flex items-center gap-2">
              <span className="num flex h-6 w-6 items-center justify-center rounded-full border border-line-strong text-[11px] text-muted group-hover:border-[var(--accent)]">{f.n}</span>
              <span className="font-semibold">{f.t}</span>
            </div>
            <p className="mt-2 text-[12.5px] leading-snug text-muted">{f.d}</p>
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1.5fr_1fr]">
        <Panel title="Projects" right={<span className="text-[12px] text-faint">{list.length} saved locally</span>}>
          {list.length === 0 ? (
            <p className="text-muted">No projects yet. Create one above or start with the drill demo.</p>
          ) : (
            <ul className="divide-y divide-[var(--line)]">
              {list.map((p) => (
                <li key={p.id} className="flex flex-wrap items-center gap-3 py-2.5">
                  <button className="min-w-0 flex-1 text-left" onClick={() => openProject(p.id).then(() => nav(p.target ? "/masking" : "/target"))}>
                    <div className="truncate font-medium">{p.name}{project?.id === p.id && <span className="ml-2 text-[11px] text-accent">open</span>}</div>
                    <div className="truncate text-[12px] text-faint">{p.target ?? "no target"} · {p.preset ?? "no environment"} · {p.updated?.replace("T", " ")}</div>
                  </button>
                  {p.rendered && <Badge tone="good">rendered</Badge>}
                  <button className="btn btn-ghost !px-2 !py-1 text-[12px]" onClick={() => remove(p.id)} aria-label={`Delete ${p.name}`}>Delete</button>
                </li>
              ))}
            </ul>
          )}
        </Panel>
        <div className="space-y-4">
          <Panel title="What masking can and cannot do">
            <ul className="space-y-2 text-[13px] leading-relaxed text-muted">
              <li><b className="text-text">It adds sound.</b> Masking never lowers the machine's sound power or level; total exposure usually rises.</li>
              <li><b className="text-text">It is perceptual.</b> Predictions are model estimates; listeners differ.</li>
              <li><b className="text-text">It is not hearing protection.</b> Never use it to hide alarms, warnings or important speech.</li>
              <li><b className="text-text">Physical levels need calibration</b> of your playback system.</li>
            </ul>
          </Panel>
          <Notice tone="accent">Low-frequency machines (generators, fans, pumps) are hard to mask with natural sound: the app will tell you when masking is expected to be ineffective or impractically loud.</Notice>
        </div>
      </div>
    </div>
  );
}
