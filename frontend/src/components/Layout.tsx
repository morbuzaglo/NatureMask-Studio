import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useStudio } from "../hooks/useStudio";
import { DomainBadge } from "./ui";

const NAV = [
  { to: "/", label: "Dashboard", step: "" },
  { to: "/target", label: "Target Noise", step: "1" },
  { to: "/soundscape", label: "Soundscape Designer", step: "2" },
  { to: "/masking", label: "Masking Laboratory", step: "3" },
  { to: "/studio", label: "Audio Studio", step: "4" },
  { to: "/export", label: "Export Center", step: "5" },
  { to: "/settings", label: "Settings", step: "" },
];

function done(step: string, p: ReturnType<typeof useStudio>["project"]) {
  if (!p) return false;
  return { "1": !!p.target, "2": !!p.scene, "3": !!p.optimization, "4": !!p.render, "5": false }[step] ?? false;
}

export function Layout() {
  const { project, mode, setMode, toasts, serverOk } = useStudio();
  const nav = useNavigate();
  return (
    <div className="flex h-full min-h-0">
      <aside className="flex w-[244px] shrink-0 flex-col border-r border-line bg-panel">
        <button className="flex items-center gap-3 px-5 pb-4 pt-5 text-left" onClick={() => nav("/")}>
          <svg width="30" height="30" viewBox="0 0 32 32" aria-hidden>
            <path d="M3 19c4-9 8 5 12-4s8 5 14-5" fill="none" stroke="var(--accent)" strokeWidth="2.6" strokeLinecap="round" />
            <path d="M3 25c4-4 8 2 12-2s8 2 14-2" fill="none" stroke="var(--target)" strokeWidth="1.6" strokeLinecap="round" opacity=".8" />
          </svg>
          <div>
            <div className="font-[family-name:var(--font-display)] text-[21px] leading-none">NatureMask</div>
            <div className="label mt-1 !text-[9.5px]">Studio · local</div>
          </div>
        </button>
        <nav className="flex flex-1 flex-col gap-0.5 px-3" aria-label="Main">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.to === "/"}
              className={({ isActive }) => `flex items-center gap-3 rounded-lg px-3 py-2 text-[13.5px] font-medium ${isActive ? "bg-raised text-text" : "text-muted hover:text-text"}`}>
              <span className="num flex h-5 w-5 items-center justify-center rounded-full text-[10.5px]"
                style={{ background: done(n.step, project) ? "var(--accent)" : "transparent", color: done(n.step, project) ? "var(--accent-ink)" : "var(--faint)",
                  border: n.step ? `1px solid ${done(n.step, project) ? "var(--accent)" : "var(--line-strong)"}` : "none" }}>
                {n.step}
              </span>
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="space-y-3 border-t border-line p-4">
          <div className="inline-flex w-full rounded-lg border border-line bg-panel-2 p-1" role="group" aria-label="Interface mode">
            {(["beginner", "expert"] as const).map((m) => (
              <button key={m} onClick={() => setMode(m)} className="tab flex-1 !py-1 text-[12px] capitalize" aria-selected={mode === m}>{m}</button>
            ))}
          </div>
          <div className="text-[11.5px] leading-snug text-faint">
            {serverOk === false ? <span style={{ color: "var(--bad)" }}>Local server not reachable</span> : "Runs entirely on this computer. No audio leaves it."}
          </div>
        </div>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center justify-between gap-4 border-b border-line bg-panel/60 px-6 backdrop-blur">
          <div className="flex min-w-0 items-center gap-3">
            <span className="label">Project</span>
            <span className="truncate font-semibold">{project?.name ?? "No project open"}</span>
            {project && <DomainBadge domain={project.target?.domain} provenance={project.target?.provenance} />}
          </div>
          <div className="text-[12px] text-faint">{project?.scene ? `Environment: ${project.scene.name}` : ""}</div>
        </header>
        <main className="scroll-thin min-h-0 flex-1 overflow-y-auto px-6 py-6 lg:px-10">
          <div className="mx-auto max-w-[1320px]"><Outlet /></div>
        </main>
      </div>
      <div className="pointer-events-none fixed bottom-5 right-5 z-50 flex w-[380px] flex-col gap-2" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className="rise pointer-events-auto rounded-lg border px-4 py-3 text-[13px] shadow-2xl"
            style={{ background: "var(--raised)", borderColor: t.kind === "error" ? "var(--bad)" : t.kind === "success" ? "var(--good)" : "var(--line-strong)" }}>
            {t.text}
          </div>
        ))}
      </div>
    </div>
  );
}
