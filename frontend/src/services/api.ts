// Typed client for the local NatureMask Studio API (same origin; dev server proxies /api).

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function req<T>(method: string, path: string, body?: unknown, isForm = false): Promise<T> {
  const init: RequestInit = { method, headers: {} };
  if (body !== undefined) {
    if (isForm) init.body = body as FormData;
    else {
      (init.headers as Record<string, string>)["Content-Type"] = "application/json";
      init.body = JSON.stringify(body);
    }
  }
  let res: Response;
  try {
    res = await fetch(`/api${path}`, init);
  } catch {
    throw new ApiError(0, "Cannot reach the local NatureMask server. Is start.bat still running?");
  }
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const j = await res.json();
      msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch {
      /* keep statusText */
    }
    throw new ApiError(res.status, msg);
  }
  return (await res.json()) as T;
}

export type Domain = "PASCAL" | "DIGITAL_CALIBRATED" | "DIGITAL_UNCALIBRATED" | "SPECTRUM_ONLY";

export interface Settings {
  fs: number; duration_s: number; seed: number; loop: boolean; loop_crossfade_s: number; preview_s: number;
  adaptive: boolean; adapt_depth_db: number; k_db: number; margin_db: number; objective: string; weights: number[];
  masker_cap_rel_db: number | null; max_mix_la: number | null; allow_eq: boolean; max_output_warning_dba: number;
}
export interface TargetMeta {
  kind: "signal" | "spectrum"; name: string; domain: Domain; provenance: string; calibrated: boolean;
  fs?: number; channels?: number; channel?: number | "mean"; duration_s?: number; representation?: string;
  tones?: { f: number; level_db: number }[]; pattern?: string; listener_distance_m?: number | null;
  calibration?: { method: string | null; k_pa_per_unit?: number; reference_LA?: number };
  meta?: { notes?: string[]; lw_conversion?: Record<string, unknown>; input_quantity?: string };
}
export interface SceneModule { id: string; type: string; enabled: boolean; level_db: number; params: Record<string, unknown>; }
export interface SceneConfig { preset: string; name: string; description: string; modules: SceneModule[];
  season?: string | null; time_of_day?: string | null; weather?: string | null; }
export interface Project {
  id: string; name: string; created: string; updated: string | null; target: TargetMeta | null; scene: SceneConfig | null;
  optimization: OptResult | null; settings: Settings; render: RenderInfo | null; notes: string;
}
export interface ProjectSummary { id: string; name: string; created: string; updated: string | null; target: string | null;
  target_domain: string | null; preset: string | null; rendered: boolean; }
export interface Catalog {
  presets: { id: string; name: string; description: string; modules: string[] }[];
  modules: { type: string; label: string; is_bed: boolean; tonal_fraction: number }[];
  modifiers: Record<string, string[]>; machine_templates: Record<string, string>; demo_targets: Record<string, string>;
  objectives: Record<string, number[]>;
  bands: { octave: { f: number[]; labels: string[] }; third: { f: number[]; labels: string[] } };
}
export interface Analysis {
  domain: Domain; provenance: string; calibrated: boolean; level_unit: string;
  levels: Record<string, number | null>; temporal: Record<string, unknown> & { class: string };
  octave: { f: number[]; labels: string[]; L: number[]; LA: number[] };
  third: { f: number[]; labels: string[]; L: number[]; LA: number[] };
  psd: { f: number[]; db: number[]; unit: string };
  tones: { frequency_hz: number; level_db: number; tnr_db?: number; pr_db?: number; prominent: boolean; tnr_criterion_db?: number; declared?: boolean }[];
  dominant_bands: string[]; difficulty: { level: string; score: number; reasons: string[]; method: string };
  waveform?: { t: number[]; min: number[]; max: number[]; unit: string };
  level_history?: { t: number[]; LAF: number[] };
  spectrogram?: { f: number[]; t: number[]; db: number[][] };
  duration_s?: number; synthetic_note?: string;
  input?: { f: number[]; L: number[]; representation: string };
}
export interface OptResult {
  model: string; objective: string; weights: number[];
  solution: { master_db: number; module_offsets_db: Record<string, number>; bed_eq_db: Record<string, number[]>; eq_bands_hz: number[] };
  terms: { masking_loss_db: number; added_level_db: number; unnaturalness_db: number };
  levels: { LA_target: number; LA_masker: number; LA_mix: number; delta_LA: number; masker_to_target_LA: number; unit: string };
  bands: { f_hz: number[]; L_target: number[]; L_masker: number[]; threshold: number[]; margin: number[]; weight: number[] };
  prominence_index_db: number; audible_band_count: number; relevant_band_count: number;
  remaining_audible: { band_hz: number; target_db: number; masker_db: number; required_masker_db: number; shortfall_db: number }[];
  feasible: boolean; notes: string[]; solver: { success: boolean; message: string; iterations: number; seconds: number };
  constraints: { max_masker_la: number | null; max_mix_la: number | null };
  pareto?: { points: ParetoPoint[]; non_dominated: ParetoPoint[] };
}
export interface ParetoPoint { w2: number; masking_loss: number; added_level: number; unnaturalness: number; LA_masker: number; feasible: boolean; }
export interface RenderInfo { fs: number; duration_s: number; n: number; seed: number; loop: boolean; adaptive: boolean; units: string;
  preview_s: number; preview_common_gain: number; target_source: { looped: boolean; label: string }; render_seconds: number; created: string; }
export interface Spectra { LAeq: number; LZeq: number; LCeq: number; octave: { f: number[]; L: number[] }; third: { f: number[]; L: number[] }; psd: { f: number[]; db: number[] }; }
export interface Evaluation {
  model: string; calibrated: boolean; level_unit: string; target: Spectra; masker: Spectra; mix: Spectra;
  third_labels: string[]; octave_labels: string[]; delta_LA: number; masker_to_target_LA: number; masker_to_target_third: number[];
  erb: { bands_hz: number[]; L_target: number[]; L_masker: number[]; threshold: number[]; margin: number[] };
  prominence_index_db: number; audible_band_count: number; band_count: number; worst_band_hz: number; worst_margin_db: number;
  assumptions: string[]; interpretation: string[];
  time_varying?: { t: number[]; pi: number[]; median: number; p90: number; max: number };
}
export interface Job<T = unknown> { id: string; kind: string; status: "queued" | "running" | "done" | "error"; progress: number; message: string; result: T | null; error: string | null; }
export interface ExportFile { file: string; format: string; valid: boolean; [k: string]: unknown }

export const api = {
  health: () => req<{ ok: boolean; version: string }>("GET", "/health"),
  catalog: () => req<Catalog>("GET", "/catalog"),
  projects: () => req<ProjectSummary[]>("GET", "/projects"),
  createProject: (name: string) => req<Project>("POST", "/projects", { name }),
  project: (id: string) => req<Project>("GET", `/projects/${id}`),
  patchProject: (id: string, body: Partial<{ name: string; notes: string; settings: Partial<Settings> }>) => req<Project>("PATCH", `/projects/${id}`, body),
  deleteProject: (id: string) => req<{ deleted: string }>("DELETE", `/projects/${id}`),
  upload: (id: string, file: File) => { const fd = new FormData(); fd.append("file", file); return req<any>("POST", `/projects/${id}/upload`, fd, true); },
  configureSignal: (id: string, body: unknown) => req<{ target: TargetMeta; analysis: Analysis }>("POST", `/projects/${id}/target/signal`, body),
  configureTable: (id: string, body: unknown) => req<{ target: TargetMeta; analysis: Analysis; warnings: string[] }>("POST", `/projects/${id}/target/table`, body),
  setSpectrum: (id: string, body: unknown) => req<{ target: TargetMeta; analysis: Analysis; warnings: string[] }>("POST", `/projects/${id}/target/spectrum`, body),
  setManual: (id: string, body: unknown) => req<{ target: TargetMeta; analysis: Analysis; warnings: string[] }>("POST", `/projects/${id}/target/manual`, body),
  setDemo: (id: string, kind: string) => req<{ target: TargetMeta; analysis: Analysis; warnings: string[] }>("POST", `/projects/${id}/target/demo`, { kind }),
  analysis: (id: string) => req<{ target: TargetMeta; analysis: Analysis }>("GET", `/projects/${id}/target/analysis`),
  setScene: (id: string, body: unknown) => req<SceneConfig>("PUT", `/projects/${id}/scene`, body),
  optimize: (id: string, body: unknown) => req<OptResult>("POST", `/projects/${id}/optimize`, body),
  generate: (id: string) => req<{ job: string }>("POST", `/projects/${id}/generate`),
  job: <T,>(jid: string) => req<Job<T>>("GET", `/jobs/${jid}`),
  evaluation: (id: string) => req<{ evaluation: Evaluation; render: RenderInfo }>("GET", `/projects/${id}/evaluation`),
  exportFiles: (id: string, body: unknown) => req<{ job: string }>("POST", `/projects/${id}/export`, body),
  listExports: (id: string) => req<{ file: string; bytes: number }[]>("GET", `/projects/${id}/exports`),
  audioUrl: (id: string, stream: string, bust: string | number) => `/api/projects/${id}/audio/${stream}?v=${bust}`,
  exportUrl: (id: string, file: string) => `/api/projects/${id}/exports/${encodeURIComponent(file)}`,
};

export async function waitJob<T>(jid: string, onProgress?: (j: Job<T>) => void): Promise<T> {
  for (;;) {
    const j = await api.job<T>(jid);
    onProgress?.(j);
    if (j.status === "done") return j.result as T;
    if (j.status === "error") throw new ApiError(500, j.error || "Job failed");
    await new Promise((r) => setTimeout(r, 400));
  }
}
