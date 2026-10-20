import { useRef, useState, type ReactNode } from "react";
import { GLOSSARY } from "./glossary";

export function Term({ k, children }: { k: keyof typeof GLOSSARY | string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const text = GLOSSARY[k as string];
  if (!text) return <>{children}</>;
  return (
    <span className="relative inline-flex items-center" onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}>
      <button type="button" className="underline decoration-dotted decoration-[var(--faint)] underline-offset-4 cursor-help"
        onFocus={() => setOpen(true)} onBlur={() => setOpen(false)} aria-label={`${String(children)}: ${text}`}>
        {children}
      </button>
      {open && (
        <span role="tooltip" className="absolute left-0 top-full z-50 mt-2 w-72 rounded-lg border border-line-strong bg-raised p-3 text-[12.5px] font-normal normal-case leading-snug tracking-normal text-text shadow-xl">
          {text}
        </span>
      )}
    </span>
  );
}

export function PageHeader({ step, title, sub, right }: { step?: string; title: string; sub?: string; right?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        {step && <div className="label mb-1">{step}</div>}
        <h1 className="font-[family-name:var(--font-display)] text-[34px] leading-tight text-text">{title}</h1>
        {sub && <p className="mt-1 max-w-3xl text-muted">{sub}</p>}
      </div>
      {right}
    </div>
  );
}

export function Panel({ title, right, children, className = "", tight }: { title?: ReactNode; right?: ReactNode; children: ReactNode; className?: string; tight?: boolean }) {
  return (
    <section className={`panel ${tight ? "p-3" : "p-5"} ${className}`}>
      {(title || right) && (
        <div className="mb-3 flex items-center justify-between gap-3">
          {title ? <h2 className="text-[13px] font-semibold tracking-wide text-text">{title}</h2> : <span />}
          {right}
        </div>
      )}
      {children}
    </section>
  );
}

export function Stat({ label, value, unit, hint, tone, term }: { label: string; value: string; unit?: string; hint?: string; tone?: "good" | "warn" | "bad" | "target" | "masker" | "mix"; term?: string }) {
  const color = tone ? `var(--${tone})` : "var(--text)";
  return (
    <div className="min-w-0 rounded-lg border border-line bg-panel-2 px-4 py-3">
      <div className="label leading-snug">{term ? <Term k={term}>{label}</Term> : label}</div>
      <div className="mt-1 flex items-baseline gap-1.5">
        <span className="num text-[22px] font-medium" style={{ color }}>{value}</span>
        {unit && <span className="text-[12px] text-muted">{unit}</span>}
      </div>
      {hint && <div className="mt-0.5 text-[11.5px] leading-snug text-faint">{hint}</div>}
    </div>
  );
}

export function Badge({ children, tone = "muted" }: { children: ReactNode; tone?: "muted" | "good" | "warn" | "bad" | "accent" | "target" | "masker" }) {
  const c = tone === "muted" ? "var(--muted)" : `var(--${tone})`;
  return <span className="chip" style={{ color: c, borderColor: `color-mix(in srgb, ${c} 45%, transparent)` }}>{children}</span>;
}

export function DomainBadge({ domain, provenance }: { domain?: string; provenance?: string }) {
  if (!domain) return <Badge>No target</Badge>;
  const map: Record<string, [string, "good" | "warn" | "accent" | "muted"]> = {
    PASCAL: ["Calibrated · Pa", "good"],
    DIGITAL_CALIBRATED: ["Calibrated · factor", "good"],
    DIGITAL_UNCALIBRATED: ["Uncalibrated · relative dB", "warn"],
    SPECTRUM_ONLY: ["Spectrum data · dB re 20 µPa", "accent"],
  };
  const [t, tone] = map[domain] || [domain, "muted"];
  return (
    <span className="inline-flex flex-wrap gap-1.5">
      <Badge tone={tone}>{t}</Badge>
      {provenance && provenance !== "MEASURED" && <Badge tone="warn">{provenance.replaceAll("_", " ").toLowerCase()}</Badge>}
    </span>
  );
}

export function Field({ label, children, hint, term }: { label: string; children: ReactNode; hint?: string; term?: string }) {
  return (
    <label className="block min-w-0">
      <span className="label mb-1.5 block">{term ? <Term k={term}>{label}</Term> : label}</span>
      {children}
      {hint && <span className="mt-1 block text-[11.5px] text-faint">{hint}</span>}
    </label>
  );
}

export function Slider({ label, value, min, max, step = 1, unit = "", onChange, disabled }: { label: string; value: number; min: number; max: number; step?: number; unit?: string; onChange: (v: number) => void; disabled?: boolean }) {
  return (
    <div className="min-w-0">
      <div className="flex items-center justify-between"><span className="text-[12px] text-muted">{label}</span><span className="num text-[12px]">{value.toFixed(step < 1 ? 2 : 0)}{unit}</span></div>
      <input type="range" min={min} max={max} step={step} value={value} disabled={disabled} onChange={(e) => onChange(parseFloat(e.target.value))} aria-label={label} />
    </div>
  );
}

export function Tabs<T extends string>({ value, onChange, items }: { value: T; onChange: (v: T) => void; items: { id: T; label: ReactNode }[] }) {
  return (
    <div role="tablist" className="inline-flex flex-wrap gap-1 rounded-lg border border-line bg-panel-2 p-1">
      {items.map((it) => (
        <button key={it.id} role="tab" aria-selected={value === it.id} className="tab" onClick={() => onChange(it.id)}>{it.label}</button>
      ))}
    </div>
  );
}

export function FileDrop({ accept, onFile, busy, label }: { accept: string; onFile: (f: File) => void; busy?: boolean; label: string }) {
  const ref = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setOver(true); }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => { e.preventDefault(); setOver(false); const f = e.dataTransfer.files?.[0]; if (f) onFile(f); }}
      className="flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed px-6 py-10 text-center transition-colors"
      style={{ borderColor: over ? "var(--accent)" : "var(--line-strong)", background: over ? "color-mix(in srgb, var(--accent) 7%, transparent)" : "var(--panel-2)" }}
    >
      <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="1.6" aria-hidden>
        <path d="M12 16V4m0 0-4 4m4-4 4 4M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" />
      </svg>
      <div className="font-semibold">{busy ? "Reading file…" : label}</div>
      <div className="text-[12px] text-muted">Drag and drop, or</div>
      <button className="btn" disabled={busy} onClick={() => ref.current?.click()}>Choose file</button>
      <input ref={ref} type="file" accept={accept} hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) onFile(f); e.target.value = ""; }} />
    </div>
  );
}

export function Progress({ value, label }: { value: number; label?: string }) {
  return (
    <div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-raised">
        <div className="h-full rounded-full bg-accent transition-[width] duration-300" style={{ width: `${Math.round(value * 100)}%` }} />
      </div>
      {label && <div className="mt-1.5 text-[12px] text-muted">{label}</div>}
    </div>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-line-strong px-6 py-12 text-center">
      <div className="font-semibold text-text">{title}</div>
      {children && <div className="mt-2 max-w-md text-muted">{children}</div>}
    </div>
  );
}

export function Notice({ tone = "warn", children }: { tone?: "warn" | "bad" | "good" | "accent"; children: ReactNode }) {
  const c = `var(--${tone})`;
  return (
    <div className="rounded-lg border px-4 py-3 text-[13px] leading-relaxed" style={{ borderColor: `color-mix(in srgb, ${c} 40%, transparent)`, background: `color-mix(in srgb, ${c} 8%, transparent)` }}>
      {children}
    </div>
  );
}
