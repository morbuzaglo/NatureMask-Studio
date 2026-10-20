import { useCallback, useEffect, useMemo, useRef, useState } from "react";

export type Rep = "octave" | "third" | "continuous";
export interface EditorValue { rep: Rep; f: number[]; L: number[] }

const OCT = [31.5, 63, 125, 250, 500, 1000, 2000, 4000, 8000, 16000];
const THIRD = [20, 25, 31.5, 40, 50, 63, 80, 100, 125, 160, 200, 250, 315, 400, 500, 630, 800, 1000, 1250, 1600, 2000, 2500, 3150, 4000, 5000, 6300, 8000, 10000, 12500, 16000, 20000];
export const BANDS: Record<"octave" | "third", number[]> = { octave: OCT, third: THIRD };

const W = 900, H = 320, PADL = 52, PADR = 14, PADT = 14, PADB = 34;
const FMIN = 18, FMAX = 22000;
const lx = (f: number) => PADL + ((Math.log10(f) - Math.log10(FMIN)) / (Math.log10(FMAX) - Math.log10(FMIN))) * (W - PADL - PADR);
const fx = (x: number) => 10 ** (Math.log10(FMIN) + ((x - PADL) / (W - PADL - PADR)) * (Math.log10(FMAX) - Math.log10(FMIN)));

function interpLog(fsrc: number[], Lsrc: number[], f: number): number {
  if (f <= fsrc[0]) return Lsrc[0];
  if (f >= fsrc[fsrc.length - 1]) return Lsrc[Lsrc.length - 1];
  for (let i = 1; i < fsrc.length; i++) {
    if (f <= fsrc[i]) {
      const a = (Math.log(f) - Math.log(fsrc[i - 1])) / (Math.log(fsrc[i]) - Math.log(fsrc[i - 1]));
      return Lsrc[i - 1] + a * (Lsrc[i] - Lsrc[i - 1]);
    }
  }
  return Lsrc[Lsrc.length - 1];
}

/** Convert between representations. Band<->band conversions preserve energy; continuous values are
 *  spectrum levels (dB per Hz), so band level = density + 10log10(bandwidth). */
export function convert(v: EditorValue, to: Rep): EditorValue {
  if (v.rep === to) return v;
  const bw = (fc: number, b: number) => fc * (10 ** (0.3 / (2 * b)) - 10 ** (-0.3 / (2 * b)));
  // to density (dB/Hz) samples
  let fd: number[], dd: number[];
  if (v.rep === "continuous") { fd = v.f; dd = v.L; }
  else { const b = v.rep === "octave" ? 1 : 3; fd = v.f; dd = v.L.map((L, i) => L - 10 * Math.log10(bw(v.f[i], b))); }
  if (to === "continuous") {
    const f = Array.from({ length: 24 }, (_, i) => 20 * (1000) ** (i / 23));
    return { rep: "continuous", f, L: f.map((x) => +interpLog(fd, dd, x).toFixed(1)) };
  }
  const b = to === "octave" ? 1 : 3;
  const f = BANDS[to];
  if (v.rep !== "continuous" && to === "octave" && v.rep === "third") {
    // exact energy sum of thirds
    const L = OCT.map((fo) => {
      const parts = v.f.map((ft, i) => ({ ft, L: v.L[i] })).filter((p) => Math.abs(Math.log2(p.ft / fo)) < 0.5);
      return parts.length ? +(10 * Math.log10(parts.reduce((s, p) => s + 10 ** (p.L / 10), 0))).toFixed(1) : 0;
    });
    return { rep: "octave", f: OCT, L };
  }
  return { rep: to, f, L: f.map((x) => +(interpLog(fd, dd, x) + 10 * Math.log10(bw(x, b))).toFixed(1)) };
}

export function SpectrumEditor({ value, onChange, unit, uncertainty, tones, onTones }: {
  value: EditorValue; onChange: (v: EditorValue) => void; unit: string; uncertainty: number; tones: { f: number; level_db: number }[];
  onTones: (t: { f: number; level_db: number }[]) => void;
}) {
  const [history, setHistory] = useState<EditorValue[]>([]);
  const [drag, setDrag] = useState<number | null>(null);
  const [sel, setSel] = useState<number | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const [yr, setYr] = useState<[number, number]>([20, 110]);

  useEffect(() => {
    const vals = [...value.L, ...tones.map((t) => t.level_db)];
    const lo = Math.floor((Math.min(...vals) - 15) / 10) * 10, hi = Math.ceil((Math.max(...vals) + 10) / 10) * 10;
    if (lo < yr[0] || hi > yr[1] || hi - lo < (yr[1] - yr[0]) - 40) setYr([lo, Math.max(hi, lo + 40)]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value.rep]);

  const ly = useCallback((L: number) => PADT + (1 - (L - yr[0]) / (yr[1] - yr[0])) * (H - PADT - PADB), [yr]);
  const yl = useCallback((y: number) => yr[0] + (1 - (y - PADT) / (H - PADT - PADB)) * (yr[1] - yr[0]), [yr]);

  const commit = (v: EditorValue) => { setHistory((h) => [...h.slice(-40), value]); onChange(v); };
  const undo = () => { const h = [...history]; const last = h.pop(); if (last) { setHistory(h); onChange(last); } };

  const point = (e: React.PointerEvent) => {
    const r = svgRef.current!.getBoundingClientRect();
    return { x: ((e.clientX - r.left) / r.width) * W, y: ((e.clientY - r.top) / r.height) * H };
  };

  const onMove = (e: React.PointerEvent) => {
    if (drag === null) return;
    const { x, y } = point(e);
    const L = Math.round(yl(y) * 2) / 2;
    const nv = { ...value, L: [...value.L], f: [...value.f] };
    nv.L[drag] = Math.max(yr[0], Math.min(yr[1], L));
    if (value.rep === "continuous") {
      const f = fx(x);
      const lo = drag > 0 ? value.f[drag - 1] * 1.02 : FMIN;
      const hi = drag < value.f.length - 1 ? value.f[drag + 1] / 1.02 : FMAX;
      nv.f[drag] = Math.round(Math.max(lo, Math.min(hi, f)));
    }
    onChange(nv);
  };

  const onDouble = (e: React.MouseEvent) => {
    if (value.rep !== "continuous") return;
    const r = svgRef.current!.getBoundingClientRect();
    const x = ((e.clientX - r.left) / r.width) * W, y = ((e.clientY - r.top) / r.height) * H;
    const f = fx(x), L = Math.round(yl(y) * 2) / 2;
    const idx = value.f.findIndex((v) => v > f);
    const i = idx < 0 ? value.f.length : idx;
    commit({ rep: "continuous", f: [...value.f.slice(0, i), Math.round(f), ...value.f.slice(i)], L: [...value.L.slice(0, i), L, ...value.L.slice(i)] });
  };

  const smooth = () => {
    const L = value.L.map((_, i) => {
      const a = value.L[Math.max(0, i - 1)], b = value.L[i], c = value.L[Math.min(value.L.length - 1, i + 1)];
      return +(0.25 * a + 0.5 * b + 0.25 * c).toFixed(1);
    });
    commit({ ...value, L });
  };

  const removeSelected = () => {
    if (sel === null || value.rep !== "continuous" || value.f.length <= 2) return;
    commit({ ...value, f: value.f.filter((_, i) => i !== sel), L: value.L.filter((_, i) => i !== sel) });
    setSel(null);
  };

  const grid = useMemo(() => {
    const ticks = [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000];
    const ys: number[] = [];
    for (let v = yr[0]; v <= yr[1]; v += 10) ys.push(v);
    return { ticks, ys };
  }, [yr]);

  const isBand = value.rep !== "continuous";
  const b = value.rep === "octave" ? 1 : 3;
  const path = value.f.map((f, i) => `${i ? "L" : "M"}${lx(f)},${ly(value.L[i])}`).join(" ");

  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <button className="btn !py-1 text-[12px]" onClick={undo} disabled={!history.length}>Undo</button>
        <button className="btn !py-1 text-[12px]" onClick={smooth}>Smooth</button>
        {value.rep === "continuous" && <button className="btn !py-1 text-[12px]" onClick={removeSelected} disabled={sel === null}>Delete point</button>}
        <button className="btn !py-1 text-[12px]" onClick={() => onTones([...tones, { f: 1000, level_db: Math.round(Math.max(...value.L)) }])}>Add tonal peak</button>
        <span className="ml-auto text-[11.5px] text-faint">
          {isBand ? "Drag bars vertically (0.5 dB steps)." : "Drag points; double-click to add; select + Delete point to remove."} Values: {unit}
        </span>
      </div>
      <svg ref={svgRef} viewBox={`0 0 ${W} ${H}`} className="w-full touch-none select-none rounded-lg border border-line bg-panel-2"
        onPointerMove={onMove} onPointerUp={() => setDrag(null)} onPointerLeave={() => setDrag(null)} onDoubleClick={onDouble}
        role="application" aria-label="Spectral editor">
        {grid.ys.map((v) => (
          <g key={v}><line x1={PADL} x2={W - PADR} y1={ly(v)} y2={ly(v)} stroke="var(--chart-grid)" />
            <text x={PADL - 8} y={ly(v) + 4} textAnchor="end" fontSize="11" fill="var(--muted)" fontFamily="IBM Plex Mono">{v}</text></g>
        ))}
        {grid.ticks.map((f) => (
          <g key={f}><line x1={lx(f)} x2={lx(f)} y1={PADT} y2={H - PADB} stroke="var(--chart-grid)" />
            <text x={lx(f)} y={H - PADB + 16} textAnchor="middle" fontSize="11" fill="var(--muted)" fontFamily="IBM Plex Mono">{f >= 1000 ? `${f / 1000}k` : f}</text></g>
        ))}
        <text x={W - PADR} y={H - 4} textAnchor="end" fontSize="11" fill="var(--faint)">Frequency (Hz)</text>
        {uncertainty > 0 && (
          <path d={value.f.map((f, i) => `${i ? "L" : "M"}${lx(f)},${ly(value.L[i] + uncertainty)}`).join(" ") + " " +
            [...value.f].reverse().map((f, j) => `L${lx(f)},${ly(value.L[value.L.length - 1 - j] - uncertainty)}`).join(" ") + "Z"}
            fill="var(--target)" opacity=".12" />
        )}
        {isBand && value.f.map((f, i) => {
          const x0 = lx(f * 10 ** (-0.3 / (2 * b))) + 1, x1 = lx(f * 10 ** (0.3 / (2 * b))) - 1;
          return (
            <g key={i} onPointerDown={(e) => { (e.target as Element).setPointerCapture?.(e.pointerId); setHistory((h) => [...h.slice(-40), value]); setDrag(i); }} style={{ cursor: "ns-resize" }}>
              <rect x={x0} y={ly(value.L[i])} width={Math.max(2, x1 - x0)} height={Math.max(0, H - PADB - ly(value.L[i]))} fill="var(--target)" opacity={drag === i ? 0.75 : 0.45} />
              <rect x={x0} y={ly(value.L[i]) - 3} width={Math.max(2, x1 - x0)} height={6} fill="var(--target)" />
              {value.rep === "octave" && <text x={(x0 + x1) / 2} y={ly(value.L[i]) - 8} textAnchor="middle" fontSize="10.5" fill="var(--text)" fontFamily="IBM Plex Mono">{value.L[i].toFixed(1)}</text>}
            </g>
          );
        })}
        {!isBand && (
          <>
            <path d={path} fill="none" stroke="var(--target)" strokeWidth="2" />
            {value.f.map((f, i) => (
              <circle key={i} cx={lx(f)} cy={ly(value.L[i])} r={sel === i ? 7 : 5.5} fill={sel === i ? "var(--text)" : "var(--target)"} stroke="var(--bg)" strokeWidth="1.5"
                style={{ cursor: "grab" }} onPointerDown={(e) => { (e.target as Element).setPointerCapture?.(e.pointerId); setSel(i); setHistory((h) => [...h.slice(-40), value]); setDrag(i); }} />
            ))}
          </>
        )}
        {tones.map((t, i) => (
          <g key={`t${i}`}>
            <line x1={lx(t.f)} x2={lx(t.f)} y1={ly(t.level_db)} y2={H - PADB} stroke="var(--bad)" strokeWidth="2" />
            <circle cx={lx(t.f)} cy={ly(t.level_db)} r="4" fill="var(--bad)" />
          </g>
        ))}
      </svg>
      {tones.length > 0 && (
        <div className="mt-3 space-y-2">
          <div className="label">Tonal peaks (narrowband components, dB re 20 µPa)</div>
          {tones.map((t, i) => (
            <div key={i} className="flex flex-wrap items-center gap-2">
              <input className="input !w-28" type="number" value={t.f} aria-label="Tone frequency (Hz)" onChange={(e) => onTones(tones.map((x, j) => j === i ? { ...x, f: +e.target.value } : x))} />
              <span className="text-[12px] text-muted">Hz</span>
              <input className="input !w-24" type="number" value={t.level_db} aria-label="Tone level (dB)" onChange={(e) => onTones(tones.map((x, j) => j === i ? { ...x, level_db: +e.target.value } : x))} />
              <span className="text-[12px] text-muted">dB</span>
              <button className="btn btn-ghost !py-1 text-[12px]" onClick={() => onTones(tones.filter((_, j) => j !== i))}>Remove</button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
