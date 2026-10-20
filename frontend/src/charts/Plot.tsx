import { useEffect, useRef } from "react";
import Plotly from "plotly.js-dist-min";
import { useStudio } from "../hooks/useStudio";

function css(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || "#888";
}

export const C = {
  target: () => css("--target"),
  masker: () => css("--masker"),
  mix: () => css("--mix"),
  threshold: () => css("--threshold"),
  text: () => css("--text"),
  muted: () => css("--muted"),
  grid: () => css("--chart-grid"),
  good: () => css("--good"),
  warn: () => css("--warn"),
  bad: () => css("--bad"),
  accent: () => css("--accent"),
};

export function baseLayout(extra: Partial<Plotly.Layout> = {}): Partial<Plotly.Layout> {
  const axis = { gridcolor: C.grid(), zerolinecolor: C.grid(), linecolor: C.grid(), tickfont: { color: C.muted(), size: 11 },
    titlefont: { color: C.muted(), size: 12 }, title: { font: { color: C.muted(), size: 12 } } };
  return {
    paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)",
    font: { family: "IBM Plex Sans, Segoe UI, sans-serif", color: C.text(), size: 12 },
    margin: { l: 56, r: 16, t: 12, b: 44 },
    legend: { orientation: "h", x: 0, y: 1.12, font: { color: C.muted(), size: 11.5 }, bgcolor: "rgba(0,0,0,0)" },
    hoverlabel: { font: { family: "IBM Plex Mono, monospace", size: 12 } },
    ...extra,
    xaxis: { ...axis, ...(extra.xaxis || {}) } as Plotly.LayoutAxis,
    yaxis: { ...axis, ...(extra.yaxis || {}) } as Plotly.LayoutAxis,
  };
}

export function Plot({ data, layout, height = 320, onClick, config }: { data: Plotly.Data[]; layout?: Partial<Plotly.Layout>; height?: number; onClick?: (e: Plotly.PlotMouseEvent) => void; config?: Partial<Plotly.Config> }) {
  const ref = useRef<HTMLDivElement>(null);
  const { theme } = useStudio();
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    Plotly.react(el, data, { ...baseLayout(layout), height, autosize: true },
      { displaylogo: false, responsive: true, modeBarButtonsToRemove: ["lasso2d", "select2d"], ...config });
    const anyEl = el as unknown as { on?: (ev: string, cb: (e: Plotly.PlotMouseEvent) => void) => void; removeAllListeners?: (ev: string) => void };
    if (onClick && anyEl.on) {
      anyEl.removeAllListeners?.("plotly_click");
      anyEl.on("plotly_click", onClick);
    }
  }, [data, layout, height, theme, onClick, config]);
  useEffect(() => {
    const el = ref.current;
    return () => { if (el) Plotly.purge(el); };
  }, []);
  return <div ref={ref} className="w-full" style={{ minHeight: height }} />;
}

export const logFreqAxis = (title = "Frequency (Hz)", range: [number, number] = [Math.log10(20), Math.log10(20000)]) => ({
  type: "log" as const, title: { text: title }, range,
  tickvals: [20, 31.5, 63, 125, 250, 500, 1000, 2000, 4000, 8000, 16000],
  ticktext: ["20", "31.5", "63", "125", "250", "500", "1k", "2k", "4k", "8k", "16k"],
});
