import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, type Analysis, type Catalog, type Project } from "../services/api";

type Mode = "beginner" | "expert";
interface Toast { id: number; kind: "info" | "error" | "success"; text: string }

interface Studio {
  catalog: Catalog | null;
  project: Project | null;
  analysis: Analysis | null;
  mode: Mode;
  theme: "dark" | "light";
  setMode: (m: Mode) => void;
  setTheme: (t: "dark" | "light") => void;
  openProject: (id: string) => Promise<void>;
  refresh: () => Promise<void>;
  setProject: (p: Project | null) => void;
  setAnalysis: (a: Analysis | null) => void;
  toast: (text: string, kind?: Toast["kind"]) => void;
  toasts: Toast[];
  serverOk: boolean | null;
}

const Ctx = createContext<Studio | null>(null);

function stored<T extends string>(key: string, fallback: T): T {
  try {
    return (localStorage.getItem(key) as T) || fallback;
  } catch {
    return fallback;
  }
}

export function StudioProvider({ children }: { children: ReactNode }) {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [project, setProject] = useState<Project | null>(null);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [mode, setModeS] = useState<Mode>(stored("nm-mode", "beginner"));
  const [theme, setThemeS] = useState<"dark" | "light">(stored("nm-theme", "dark"));
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [serverOk, setServerOk] = useState<boolean | null>(null);

  const toast = useCallback((text: string, kind: Toast["kind"] = "info") => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, kind, text }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), kind === "error" ? 9000 : 4500);
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem("nm-theme", theme); } catch { /* ignore */ }
  }, [theme]);

  useEffect(() => {
    api.health().then(() => setServerOk(true)).catch(() => setServerOk(false));
    api.catalog().then(setCatalog).catch((e) => toast(e.message, "error"));
    const last = stored("nm-last-project", "");
    if (last) openProject(last).catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const openProject = useCallback(async (id: string) => {
    const p = await api.project(id);
    setProject(p);
    setAnalysis(null);
    try { localStorage.setItem("nm-last-project", id); } catch { /* ignore */ }
    if (p.target) {
      try {
        setAnalysis((await api.analysis(id)).analysis);
      } catch { /* analysis can fail for corrupt data; UI shows empty state */ }
    }
  }, []);

  const refresh = useCallback(async () => {
    if (project) setProject(await api.project(project.id));
  }, [project]);

  const value = useMemo<Studio>(() => ({
    catalog, project, analysis, mode, theme, toasts, serverOk,
    setMode: (m) => { setModeS(m); try { localStorage.setItem("nm-mode", m); } catch { /* ignore */ } },
    setTheme: setThemeS, openProject, refresh, setProject, setAnalysis, toast,
  }), [catalog, project, analysis, mode, theme, toasts, serverOk, openProject, refresh, toast]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useStudio(): Studio {
  const c = useContext(Ctx);
  if (!c) throw new Error("StudioProvider missing");
  return c;
}

export function fmt(v: number | null | undefined, digits = 1, unit = ""): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return "—";
  return `${v.toFixed(digits)}${unit}`;
}
export function signed(v: number | null | undefined, digits = 1): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return "—";
  return `${v >= 0 ? "+" : "−"}${Math.abs(v).toFixed(digits)}`;
}
