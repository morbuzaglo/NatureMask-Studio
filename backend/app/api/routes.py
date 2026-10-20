"""REST API for NatureMask Studio (local only)."""
from __future__ import annotations

import io
import logging
import math
import os

import numpy as np
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from .. import engine
from ..acoustics.bands import band_centres, nominal_label
from ..exports.exporters import export as do_export
from ..generation import analysis_window_s, generate as do_generate
from ..io import importers
from ..optimization.optimizer import OBJECTIVES, OptimizeRequest, optimize_masking
from ..storage import projects as store
from ..synthesis.presets import MODIFIERS, build_scene_config, list_presets
from ..synthesis.scene import MODULE_TYPES, module_catalog
from ..synthesis.target_synth import demo_machine_spectrum
from . import jobs

log = logging.getLogger("naturemask.api")
router = APIRouter(prefix="/api")
MAX_UPLOAD = 1024 * 1024 * 1024  # 1 GB


def clean(o):
    """JSON-safe conversion: numpy -> python, NaN/Inf -> None."""
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, np.ndarray):
        return clean(o.tolist())
    if isinstance(o, (np.floating, float)):
        f = float(o)
        return f if math.isfinite(f) else None
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o


def ok(data):
    return JSONResponse(clean(data))


def _proj(pid):
    try:
        return store.load(pid)
    except KeyError:
        raise HTTPException(404, "Project not found")


def _target_arrays(pid, proj):
    if not proj.get("target"):
        raise HTTPException(400, "Define the target noise first (Target Noise page).")
    return proj["target"], store.load_arrays(pid, "target")


# ------------------------------------------------------------------------------------------ catalogue

@router.get("/health")
def health():
    return {"ok": True, "app": "NatureMask Studio", "version": "0.1.0", "offline": True}


@router.get("/catalog")
def catalog():
    fo, _, _ = band_centres(1, 31.5, 16000)
    ft, _, _ = band_centres(3, 20, 20000)
    return ok({"presets": list_presets(), "modules": module_catalog(), "modifiers": {k: list(v) for k, v in MODIFIERS.items()},
               "machine_templates": {k: v["label"] for k, v in engine.MACHINE_TEMPLATES.items()},
               "demo_targets": {"drill": "Electric drill (synthetic)", "grinder_hf": "High-frequency grinder (synthetic)",
                                "generator_lf": "Generator — low-frequency (synthetic)", "fan": "Fan (synthetic)"},
               "objectives": {k: list(v) for k, v in OBJECTIVES.items()},
               "bands": {"octave": {"f": fo, "labels": [nominal_label(x) for x in fo]},
                         "third": {"f": ft, "labels": [nominal_label(x) for x in ft]}}})


# ------------------------------------------------------------------------------------------ projects

class NewProject(BaseModel):
    name: str = "Untitled project"


@router.get("/projects")
def list_projects():
    return ok(store.list_projects())


@router.post("/projects")
def create_project(body: NewProject):
    return ok(store.create(body.name))


@router.get("/projects/{pid}")
def get_project(pid: str):
    return ok(_proj(pid))


class ProjectPatch(BaseModel):
    name: str | None = None
    notes: str | None = None
    settings: dict | None = None


@router.patch("/projects/{pid}")
def patch_project(pid: str, body: ProjectPatch):
    p = _proj(pid)
    if body.name is not None:
        p["name"] = body.name
    if body.notes is not None:
        p["notes"] = body.notes
    if body.settings is not None:
        s = dict(p["settings"])
        s.update(body.settings)
        if float(s.get("duration_s", 60)) < 10:
            raise HTTPException(400, "Minimum duration is 10 s.")
        if int(s.get("fs", 48000)) not in (44100, 48000, 96000):
            raise HTTPException(400, "Sample rate must be 44100, 48000 or 96000 Hz.")
        p["settings"] = s
    return ok(store.save(p))


@router.delete("/projects/{pid}")
def delete_project(pid: str):
    _proj(pid)
    store.delete(pid)
    return {"deleted": pid}


# ------------------------------------------------------------------------------------------ target input

@router.post("/projects/{pid}/upload")
async def upload(pid: str, file: UploadFile = File(...)):
    p = _proj(pid)
    raw = await file.read()
    if len(raw) > MAX_UPLOAD:
        raise HTTPException(413, "File too large (limit 1 GB).")
    name = (file.filename or "upload").lower()
    d = store.project_dir(pid)
    try:
        if name.endswith(".mat"):
            r = importers.load_mat(raw)
        elif name.endswith((".wav", ".flac", ".ogg")):
            r = importers.load_audio(raw)
        elif name.endswith((".csv", ".txt", ".xlsx", ".xlsm", ".xls")):
            t = importers.load_table(raw, name)
            df = t.pop("_df")
            df.to_csv(os.path.join(d, "pending_table.csv"), index=False)
            return ok({"kind": "table", "file": file.filename, **t})
        else:
            raise importers.ImportErrorUser("Unsupported file type. Use .mat, .wav/.flac, .csv, .xlsx or .xls.")
    except importers.ImportErrorUser as e:
        raise HTTPException(400, str(e))
    sig = r["sig"]
    np.savez(os.path.join(d, "pending_signal.npz"), sig=sig, fs=np.array(r["fs"] if r["fs"] else np.nan))
    peak = float(np.max(np.abs(sig))) if sig.size else 0.0
    return ok({"kind": "signal", "file": file.filename, "format": r["format"], "variables": r.get("variables"),
               "sig_name": r.get("sig_name"), "fs": r["fs"], "fs_name": r.get("fs_name"), "samples": sig.shape[0],
               "channels": sig.shape[1], "duration_s": (sig.shape[0] / r["fs"]) if r["fs"] else None,
               "peak": peak, "meta": r["meta"], "suggested_domain": r["suggested_domain"],
               "channel_rms": np.sqrt(np.mean(sig ** 2, axis=0)).tolist()})


class SignalConfig(BaseModel):
    domain: str
    k_pa_per_unit: float | None = None
    reference_la: float | None = None
    channel: int | str | None = 0
    fs: float | None = None
    name: str = "Recording"


@router.post("/projects/{pid}/target/signal")
def configure_signal(pid: str, body: SignalConfig):
    p = _proj(pid)
    d = store.project_dir(pid)
    pend = os.path.join(d, "pending_signal.npz")
    if not os.path.exists(pend):
        raise HTTPException(400, "Upload a recording first.")
    with np.load(pend) as z:
        sig, fs = z["sig"], float(z["fs"])
    if body.fs:
        fs = float(body.fs)
    if not fs or not math.isfinite(fs):
        raise HTTPException(400, "Sampling frequency unknown: enter fs (Hz).")
    if body.channel not in (None, "mean") and int(body.channel) >= sig.shape[1]:
        raise HTTPException(400, "Channel index out of range.")
    ch = None if body.channel == "mean" else (int(body.channel) if body.channel is not None else 0)
    try:
        meta, arr = engine.target_from_signal(sig, fs, body.domain, body.k_pa_per_unit, ch, body.name,
                                              reference_la=body.reference_la)
    except ValueError as e:
        raise HTTPException(400, str(e))
    meta["channel"] = "mean" if ch is None else ch
    store.save_arrays(pid, "target", **arr)
    p["target"] = meta
    p["optimization"] = None
    p["render"] = None
    store.save(p)
    return ok({"target": meta, "analysis": engine.analyze_target(meta, arr, int(p["settings"]["fs"]))})


class TableConfig(BaseModel):
    frequency_column: str
    level_column: str
    representation: str | None = None
    quantity: str = "Lp"
    a_weighted: bool = False
    distance_m: float | None = None
    field: str = "hemispherical"
    directivity_db: float = 0.0
    air_absorption: bool = False
    pattern: str = "stationary"
    name: str = "Spectrum table"
    measured_at_m: float | None = None


@router.post("/projects/{pid}/target/table")
def configure_table(pid: str, body: TableConfig):
    import pandas as pd
    p = _proj(pid)
    path = os.path.join(store.project_dir(pid), "pending_table.csv")
    if not os.path.exists(path):
        raise HTTPException(400, "Upload a table first.")
    df = pd.read_csv(path)
    try:
        spec = importers.table_to_spectrum(df, body.frequency_column, body.level_column, body.representation, False)
        meta, arr = engine.target_from_spectrum(spec["f"], spec["L"], spec["representation"], body.quantity,
                                                body.distance_m, body.field, body.directivity_db, body.air_absorption,
                                                pattern=body.pattern, name=body.name, a_weighted=body.a_weighted,
                                                notes=spec["warnings"], measured_at_m=body.measured_at_m)
    except (ValueError, importers.ImportErrorUser) as e:
        raise HTTPException(400, str(e))
    return _store_spectrum(pid, p, meta, arr, spec["warnings"])


class SpectrumBody(BaseModel):
    f: list[float]
    L: list[float]
    representation: str  # octave | third | continuous
    quantity: str = "Lp"  # Lp | Lw
    a_weighted: bool = False
    distance_m: float | None = None
    field: str = "hemispherical"
    directivity_db: float = 0.0
    air_absorption: bool = False
    tones: list[dict] = []
    pattern: str = "stationary"
    provenance: str = "MEASURED"
    name: str = "Spectrum"
    uncertainty_db: float | None = None
    measured_at_m: float | None = None


@router.post("/projects/{pid}/target/spectrum")
def set_spectrum(pid: str, body: SpectrumBody):
    p = _proj(pid)
    if len(body.f) != len(body.L) or len(body.f) < 2:
        raise HTTPException(400, "Need matching frequency and level lists (at least 2 points).")
    try:
        meta, arr = engine.target_from_spectrum(body.f, body.L, body.representation, body.quantity, body.distance_m,
                                                body.field, body.directivity_db, body.air_absorption, body.tones,
                                                body.pattern, body.name, body.provenance, body.a_weighted,
                                                measured_at_m=body.measured_at_m)
    except ValueError as e:
        raise HTTPException(400, str(e))
    meta["uncertainty_db"] = body.uncertainty_db
    return _store_spectrum(pid, p, meta, arr, [])


class ManualBody(BaseModel):
    la: float | None = None
    lz: float | None = None
    lc: float | None = None
    template: str = "broadband"
    distance_m: float | None = None
    listener_m: float | None = None
    operating_mode: str = ""
    uncertainty_db: float | None = None
    pattern: str = "stationary"
    name: str = "Manual values"


@router.post("/projects/{pid}/target/manual")
def set_manual(pid: str, body: ManualBody):
    p = _proj(pid)
    if body.la is None:
        raise HTTPException(400, "Enter at least the A-weighted overall level (dBA).")
    if body.template not in engine.MACHINE_TEMPLATES:
        raise HTTPException(400, "Unknown machine template.")
    fm, L, tones = engine.template_spectrum(body.template, body.la)
    notes = [f"Spectrum ESTIMATED from template '{engine.MACHINE_TEMPLATES[body.template]['label']}' scaled to "
             f"LA = {body.la} dB. A single dBA value does not define a unique spectrum."]
    meta, arr = engine.target_from_spectrum(fm, L, "third", "Lp", body.listener_m, tones=tones, pattern=body.pattern,
                                            name=body.name, provenance="ESTIMATED_FROM_TEMPLATE", notes=notes,
                                            measured_at_m=body.distance_m)
    meta["manual"] = body.model_dump()
    meta["uncertainty_db"] = body.uncertainty_db
    warn = list(notes)
    if body.lc is not None:
        from ..acoustics.bands import total_from_bands
        lc_model = total_from_bands(fm, L, "C")
        if abs(lc_model - body.lc) > 3:
            warn.append(f"Entered LC = {body.lc} dB differs from the template's LC = {lc_model:.1f} dB by more than 3 dB: "
                        "the template shape may not fit this machine (consider entering band levels).")
    return _store_spectrum(pid, p, meta, arr, warn)


class DemoBody(BaseModel):
    kind: str


@router.post("/projects/{pid}/target/demo")
def set_demo(pid: str, body: DemoBody):
    p = _proj(pid)
    try:
        fm, L, tones, pattern = demo_machine_spectrum(body.kind)
    except ValueError:
        raise HTTPException(400, "Unknown demo target.")
    meta, arr = engine.target_from_spectrum(fm, L, "third", tones=tones, pattern=pattern,
                                            name=f"Demo: {body.kind} (synthetic)", provenance="SYNTHETIC",
                                            notes=["Clearly synthetic demonstration target — not a measurement."])
    return _store_spectrum(pid, p, meta, arr, [])


def _store_spectrum(pid, p, meta, arr, warnings):
    store.save_arrays(pid, "target", **arr)
    p["target"] = meta
    p["optimization"] = None
    p["render"] = None
    store.save(p)
    return ok({"target": meta, "warnings": warnings, "analysis": engine.analyze_target(meta, arr, int(p["settings"]["fs"]))})


@router.get("/projects/{pid}/target/analysis")
def target_analysis(pid: str):
    p = _proj(pid)
    meta, arr = _target_arrays(pid, p)
    out = engine.analyze_target(meta, arr, int(p["settings"]["fs"]))
    if meta["kind"] == "spectrum":
        out["input"] = {"f": arr["f"], "L": arr["L"], "representation": meta["representation"]}
    return ok({"target": meta, "analysis": out})


# ------------------------------------------------------------------------------------------ scene

class SceneBody(BaseModel):
    preset: str | None = None
    season: str | None = None
    time_of_day: str | None = None
    weather: str | None = None
    modules: list[dict] | None = None


@router.put("/projects/{pid}/scene")
def set_scene(pid: str, body: SceneBody):
    p = _proj(pid)
    if body.preset:
        try:
            cfg = build_scene_config(body.preset, body.season, body.time_of_day, body.weather)
        except ValueError as e:
            raise HTTPException(400, str(e))
    else:
        cfg = dict(p.get("scene") or {"preset": "custom", "name": "Custom Environment", "description": "", "modules": []})
    if body.modules is not None:
        mods = []
        for i, m in enumerate(body.modules):
            if m.get("type") not in MODULE_TYPES:
                raise HTTPException(400, f"Unknown sound module {m.get('type')}")
            mods.append({"id": m.get("id") or f"{m['type']}_{i}", "type": m["type"], "enabled": bool(m.get("enabled", True)),
                         "level_db": float(m.get("level_db", 0)), "params": dict(m.get("params", {}))})
        cfg["modules"] = mods
    p["scene"] = cfg
    p["optimization"] = None
    store.save(p)
    return ok(cfg)


# ------------------------------------------------------------------------------------------ optimize

class OptimizeBody(BaseModel):
    objective: str | None = None
    weights: list[float] | None = None
    margin_db: float | None = None
    k_db: float | None = None
    max_masker_la: float | None = None
    masker_cap_rel_db: float | None = None
    max_mix_la: float | None = None
    allow_eq: bool | None = None
    pareto: bool = False


@router.post("/projects/{pid}/optimize")
def optimize(pid: str, body: OptimizeBody):
    p = _proj(pid)
    meta, arr = _target_arrays(pid, p)
    if not p.get("scene") or not [m for m in p["scene"]["modules"] if m.get("enabled", True)]:
        raise HTTPException(400, "Choose an environment with at least one enabled sound module first.")
    s = p["settings"]
    fs = int(s["fs"])
    f, psd = engine.target_psd(meta, arr, fs)
    from ..acoustics.bands import total_from_psd
    from ..acoustics.levels import P0
    la_t = total_from_psd(f, psd, P0 if meta["calibrated"] else 1.0, "A")
    # an explicitly sent null means "no cap"; an omitted field falls back to the project setting
    cap_rel = body.masker_cap_rel_db if "masker_cap_rel_db" in body.model_fields_set else s.get("masker_cap_rel_db", 3.0)
    max_m = body.max_masker_la if body.max_masker_la is not None else (la_t + cap_rel if cap_rel is not None else None)
    tones = [t["f"] for t in meta.get("tones", [])]
    if meta["kind"] == "signal":
        from ..dsp import spectral
        an = engine.analyze_target(meta, arr, fs)
        tones = [t["frequency_hz"] for t in an["tones"] if t.get("prominent")]
    req = OptimizeRequest(f=f, target_psd=psd, calibrated=bool(meta["calibrated"]), scene_config=p["scene"], fs=fs,
                          seed=int(s["seed"]), objective=body.objective or s["objective"],
                          weights=tuple(body.weights or s.get("weights") or (1, 1, 0.5)),
                          margin_db=body.margin_db if body.margin_db is not None else s["margin_db"],
                          k_db=body.k_db if body.k_db is not None else s["k_db"],
                          max_masker_la=max_m,
                          max_mix_la=body.max_mix_la if "max_mix_la" in body.model_fields_set else s.get("max_mix_la"),
                          allow_eq=body.allow_eq if body.allow_eq is not None else s.get("allow_eq", True),
                          tonal_bands_hz=tones, analysis_s=analysis_window_s(float(s["duration_s"])))
    try:
        r = optimize_masking(req, pareto=body.pareto)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if meta["calibrated"] and r["levels"]["LA_mix"] > float(s.get("max_output_warning_dba", 80)):
        r["notes"].append(f"Combined level {r['levels']['LA_mix']:.1f} dBA exceeds the warning limit "
                          f"({s.get('max_output_warning_dba', 80)} dBA). Consider hearing-health implications.")
    p["optimization"] = r
    store.save(p)
    return ok(r)


# ------------------------------------------------------------------------------------------ generate / evaluate

@router.post("/projects/{pid}/generate")
def generate(pid: str):
    p = _proj(pid)
    meta, arr = _target_arrays(pid, p)
    if not p.get("scene"):
        raise HTTPException(400, "Choose an environment first.")
    settings = dict(p["settings"])

    def work(progress):
        res = do_generate(store.project_dir(pid), meta, arr, p["scene"], p.get("optimization"), settings, progress)
        q = store.load(pid)
        q["render"] = res["render"]
        store.save(q)
        return {"render": res["render"], "evaluation_summary": {k: res["evaluation"][k] for k in
                ("delta_LA", "masker_to_target_LA", "prominence_index_db", "audible_band_count", "band_count")}}
    return {"job": jobs.submit("generate", work)}


@router.get("/jobs/{jid}")
def job(jid: str):
    try:
        return ok(jobs.get(jid))
    except KeyError:
        raise HTTPException(404, "Job not found")


@router.get("/projects/{pid}/evaluation")
def evaluation(pid: str):
    p = _proj(pid)
    path = os.path.join(store.project_dir(pid), "render", "evaluation.json")
    if not os.path.exists(path):
        raise HTTPException(404, "Generate a soundscape first.")
    import json
    with open(path, encoding="utf-8") as fh:
        return ok({"evaluation": json.load(fh), "render": p.get("render")})


@router.get("/projects/{pid}/audio/{stream}")
def audio(pid: str, stream: str):
    if stream not in ("target", "masker", "mix"):
        raise HTTPException(404, "Unknown stream")
    path = os.path.join(store.project_dir(pid), "render", f"preview_{stream}.wav")
    if not os.path.exists(path):
        raise HTTPException(404, "Generate a soundscape first.")
    return FileResponse(path, media_type="audio/wav", headers={"Cache-Control": "no-store"})


# ------------------------------------------------------------------------------------------ export

class ExportBody(BaseModel):
    formats: list[str] = ["wav24", "mat"]
    stream: str = "masker"
    channels: int = 2
    mat_signal_domain: str = "digital"
    preserve_relative_level: bool = True
    basename: str | None = None


@router.post("/projects/{pid}/export")
def export(pid: str, body: ExportBody):
    p = _proj(pid)
    meta, arr = _target_arrays(pid, p)
    if not p.get("render"):
        raise HTTPException(400, "Generate a soundscape first.")
    if body.mat_signal_domain == "pascal" and not meta["calibrated"]:
        raise HTTPException(400, "Pressure (Pa) export needs a calibrated target.")
    import json
    with open(os.path.join(store.project_dir(pid), "render", "evaluation.json"), encoding="utf-8") as fh:
        ev = json.load(fh)
    opts = body.model_dump()
    opts["basename"] = body.basename or "".join(c if c.isalnum() else "_" for c in p["name"])[:40] or "naturemask"

    def work(progress):
        progress(0.1, "Writing files")
        files = do_export(store.project_dir(pid), meta, arr, p["render"], ev, opts)
        return {"files": files}
    return {"job": jobs.submit("export", work)}


@router.get("/projects/{pid}/exports")
def list_exports(pid: str):
    d = os.path.join(store.project_dir(pid), "exports")
    if not os.path.isdir(d):
        return []
    return [{"file": f, "bytes": os.path.getsize(os.path.join(d, f))} for f in sorted(os.listdir(d))]


@router.get("/projects/{pid}/exports/{name}")
def get_export(pid: str, name: str):
    if "/" in name or "\\" in name or name.startswith("."):
        raise HTTPException(400, "Bad file name")
    path = os.path.join(store.project_dir(pid), "exports", name)
    if not os.path.exists(path):
        raise HTTPException(404, "Not found")
    return FileResponse(path, filename=name)
