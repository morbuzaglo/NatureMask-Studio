"""Chunked soundscape generation to disk, preview streams, and masking evaluation from the actual audio."""
from __future__ import annotations

import io
import json
import math
import os
import time
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

import numpy as np
import soundfile as sf

from .acoustics import bands as B
from .acoustics.levels import P0, a_weighting_db
from .dsp import spectral
from .engine import analysis_grid, target_audio_block_source, target_psd
from .optimization.optimizer import adaptation_curve
from .psychoacoustics import masking
from .synthesis.core import derive_seed
from .synthesis.scene import ADAPT_RATE, MODULE_TYPES, Scene

PEAK_TARGET = 10 ** (-1 / 20)  # -1 dBFS
ANALYSIS_WINDOW_S = 60.0


def analysis_window_s(duration_s: float) -> float:
    """Window [0, T) used both by the optimizer's module analysis and by the evaluation."""
    return float(min(duration_s, ANALYSIS_WINDOW_S))


def generate(project_dir: str, meta: dict, arrays: dict, scene_cfg: dict, opt: dict | None, settings: dict,
             progress=lambda p, msg="": None) -> dict:
    """Render masker (target units) to <project>/render/masker.f32, plus preview WAVs with a COMMON gain
    so the relative level of target / masker / mix is preserved."""
    fs = int(settings.get("fs", 48000))
    dur = float(settings.get("duration_s", 60))
    if dur < 10:
        raise ValueError("Minimum duration is 10 s.")
    seed = int(settings.get("seed", 1))
    loop = bool(settings.get("loop", False))
    xfade = int(float(settings.get("loop_crossfade_s", 3.0)) * fs) if loop else 0
    preview_s = float(settings.get("preview_s", 60))
    adapt = bool(settings.get("adaptive", False))
    rdir = os.path.join(project_dir, "render")
    os.makedirs(rdir, exist_ok=True)
    sol = (opt or {}).get("solution", {})
    adaptation = None
    if adapt and meta["kind"] == "signal":
        from .engine import select_channel, to_units
        from .acoustics.levels import apply_weighting
        x = to_units(meta, select_channel(meta, arrays["sig"]))
        tt, la = spectral.short_time_levels(apply_weighting(x, meta["fs"], "A"), meta["fs"],
                                            P0 if meta["calibrated"] else 1.0, 0.5)
        _, adaptation = adaptation_curve(tt, la, depth_db=float(settings.get("adapt_depth_db", 6)),
                                         rate_hz=ADAPT_RATE, duration_s=dur + 10)
        if len(x) / meta["fs"] < dur:  # periodic extension to match the looped target recording
            per = int(len(x) / meta["fs"] * ADAPT_RATE)
            reps = int(math.ceil(len(adaptation) / max(per, 1)))
            adaptation = np.tile(adaptation[:per], reps)[: int((dur + 10) * ADAPT_RATE)]
    scene = Scene(scene_cfg, fs, dur, seed, master_db=sol.get("master_db", 0.0),
                  module_gains_db=sol.get("module_offsets_db"), bed_eq=sol.get("bed_eq_db"),
                  adaptation_db=adaptation, extra_s=xfade / fs + 1)
    n_out = int(round(dur * fs))
    n_render = n_out + xfade
    path = os.path.join(rdir, "masker.f32")
    mm = np.lib.format.open_memmap(path + ".npy", mode="w+", dtype=np.float32, shape=(n_render, 2))
    chunk = fs * 5
    t0 = time.time()
    pos = 0
    while pos < n_render:
        m = min(chunk, n_render - pos)
        mm[pos:pos + m] = scene.render(pos, m)
        pos += m
        progress(0.85 * pos / n_render, f"Rendering soundscape {pos / fs:.0f}/{n_render / fs:.0f} s")
    if loop:
        w = np.linspace(0, math.pi / 2, xfade, dtype=np.float32)[:, None]
        head = mm[:xfade].copy()
        mm[:xfade] = head * np.sin(w) + mm[n_out:n_out + xfade] * np.cos(w)
    mm.flush()
    del mm
    masker = np.load(path + ".npy", mmap_mode="r")[:n_out]
    tsrc, tinfo = target_audio_block_source(meta, arrays, fs, seed, dur)
    # peaks over the full duration (chunked)
    pk = {"target": 0.0, "masker": 0.0, "mix": 0.0}
    pos = 0
    while pos < n_out:
        m = min(chunk, n_out - pos)
        tg = tsrc(pos, m)[:, None]
        mk = np.asarray(masker[pos:pos + m], dtype=np.float64)
        pk["target"] = max(pk["target"], float(np.max(np.abs(tg))))
        pk["masker"] = max(pk["masker"], float(np.max(np.abs(mk))))
        pk["mix"] = max(pk["mix"], float(np.max(np.abs(mk + tg))))
        pos += m
        progress(0.85 + 0.1 * pos / n_out, "Measuring peaks")
    common_gain = PEAK_TARGET / max(pk.values()) if max(pk.values()) > 0 else 1.0
    # preview WAVs (first preview_s), 16-bit stereo, common gain
    npv = min(n_out, int(preview_s * fs))
    tg = tsrc(0, npv)[:, None] * np.ones((1, 2))
    mk = np.asarray(masker[:npv], dtype=np.float64)
    for name, data in (("target", tg), ("masker", mk), ("mix", tg + mk)):
        sf.write(os.path.join(rdir, f"preview_{name}.wav"), np.clip(data * common_gain, -1, 1), fs, subtype="PCM_16")
    info = {"fs": fs, "duration_s": dur, "n": n_out, "channels": 2, "seed": seed, "loop": loop,
            "loop_crossfade_s": xfade / fs, "adaptive": adaptation is not None,
            "units": "Pa" if meta["calibrated"] else "FS (relative to target recording)",
            "peaks_units": pk, "preview_common_gain": common_gain, "preview_s": npv / fs,
            "target_source": tinfo, "render_seconds": round(time.time() - t0, 2),
            "scene": scene_cfg, "solution": sol, "created": time.strftime("%Y-%m-%dT%H:%M:%S")}
    with open(os.path.join(rdir, "render.json"), "w", encoding="utf-8") as fh:
        json.dump(info, fh, indent=1, default=float)
    progress(0.97, "Evaluating masking")
    ev = evaluate(project_dir, meta, arrays, info, settings)
    with open(os.path.join(rdir, "evaluation.json"), "w", encoding="utf-8") as fh:
        json.dump(ev, fh, default=float)
    progress(1.0, "Done")
    return {"render": info, "evaluation": ev}


AUDITION_S = 20.0
AUDITION_MAX_FS = 48000
AUDITION_FADE_S = 0.05


@lru_cache(maxsize=16)
def _module_audio_cached(mtype: str, params_key: str, seed: int, fs: int, seconds: float) -> np.ndarray:
    params = json.loads(params_key)
    mod = MODULE_TYPES[mtype](fs, seed, params, seconds + 5)
    return mod.render(0, int(seconds * fs)).astype(np.float32)


def _module_audio(m: dict, fs: int, scene_seed: int, seconds: float) -> np.ndarray:
    """Module audio at 0 dB level, seeded exactly as Scene seeds it (same id + scene seed = same sound)."""
    params = dict(m.get("params", {}))
    params.setdefault("gust_seed", derive_seed(scene_seed, "gusts"))
    return _module_audio_cached(m["type"], json.dumps(params, sort_keys=True), derive_seed(scene_seed, m["id"]),
                                int(fs), float(seconds))


def audition(modules: list, settings: dict, solo: str | None = None) -> tuple[bytes, dict]:
    """Short WAV of the designer's sources (no optimizer gains, no machine). A soloed source uses the SAME
    gain as the mix of all enabled sources, so the per-source level balance stays audible between solos."""
    fs = min(int(settings.get("fs", 48000)), AUDITION_MAX_FS)
    seed = int(settings.get("seed", 1))
    mix_ids = [m["id"] for m in modules if m.get("enabled", True)]
    if solo is not None and solo not in {m["id"] for m in modules}:
        raise ValueError(f"Unknown source {solo}")
    wanted = [m for m in modules if m["id"] in mix_ids or m["id"] == solo]
    if not wanted:
        raise ValueError("Enable at least one sound source.")
    with ThreadPoolExecutor(max_workers=min(4, len(wanted))) as ex:
        audio = dict(zip([m["id"] for m in wanted],
                         ex.map(lambda m: _module_audio(m, fs, seed, AUDITION_S), wanted)))
    gains = {m["id"]: 10 ** (float(m.get("level_db", 0)) / 20) for m in wanted}
    n = int(AUDITION_S * fs)
    mix = np.zeros((n, 2))
    for i in mix_ids:
        mix += audio[i] * gains[i]
    out = audio[solo] * gains[solo] if solo is not None else mix
    peak = max(float(np.max(np.abs(mix))), float(np.max(np.abs(out))))
    out = out * (PEAK_TARGET / peak if peak > 0 else 1.0)
    nf = int(AUDITION_FADE_S * fs)
    ramp = np.linspace(0, 1, nf)[:, None]
    out[:nf] *= ramp
    out[-nf:] *= ramp[::-1]
    buf = io.BytesIO()
    sf.write(buf, np.clip(out, -1, 1), fs, format="WAV", subtype="PCM_16")
    with np.errstate(divide="ignore"):
        rms_db = float(10 * np.log10(np.mean(out ** 2)))
    return buf.getvalue(), {"fs": fs, "seconds": AUDITION_S, "rms_dbfs": rms_db, "silent": not rms_db > -80}


def load_masker(project_dir: str):
    return np.load(os.path.join(project_dir, "render", "masker.f32.npy"), mmap_mode="r")


def evaluate(project_dir: str, meta: dict, arrays: dict, info: dict, settings: dict | None = None) -> dict:
    """Masking evaluation using the actually rendered masker (long-term PSD, per-channel average)."""
    settings = settings or {}
    fs = info["fs"]
    cal = bool(meta["calibrated"])
    ref = P0 if cal else 1.0
    masker = load_masker(project_dir)[: info["n"]]
    n_an = int(analysis_window_s(info["duration_s"]) * fs)  # same window the optimizer analysed
    seg = np.asarray(masker[:n_an], dtype=np.float64)
    # full-duration time-domain LAeq of the masker (reveals any drift beyond the analysis window)
    from .acoustics.levels import apply_weighting
    acc, pos = 0.0, 0
    while pos < info["n"]:
        blk = np.asarray(masker[pos:pos + fs * 30], dtype=np.float64)
        acc += float(np.sum(apply_weighting(blk, fs, "A") ** 2))
        pos += blk.shape[0]
    la_full = 10 * np.log10(max(acc / (2 * info["n"]), 1e-300) / ref ** 2)
    fL, pL = spectral.welch_psd(seg[:, 0], fs, 0.5)
    _, pR = spectral.welch_psd(seg[:, 1], fs, 0.5)
    pm = 0.5 * (pL + pR)
    ft, pt = target_psd(meta, arrays, fs)
    pt = np.interp(fL, ft, pt)
    f = fL
    params = masking.MaskingParams(k_db=float(settings.get("k_db", -4.0)), margin_db=float(settings.get("margin_db", 3.0)))
    est = masking.estimate(f, pt, pm, ref, cal, params, fs)
    res = {"model": est["model"], "calibrated": cal,
           "level_unit": "dB re 20 µPa" if cal else "dB relative (uncalibrated)"}
    for name, p in (("target", pt), ("masker", pm), ("mix", pt + pm)):
        fo, Lo = B.band_levels_from_psd(f, p, ref, 1, 31.5, 16000)
        f3, L3 = B.band_levels_from_psd(f, p, ref, 3, 20, 20000)
        step = max(1, len(f) // 1500)
        with np.errstate(divide="ignore"):
            psd_db = 10 * np.log10(np.maximum(p[1::step], 1e-300) / ref ** 2)
        res[name] = {"LAeq": B.total_from_psd(f, p, ref, "A"), "LZeq": B.total_from_psd(f, p, ref, "Z"),
                     "LCeq": B.total_from_psd(f, p, ref, "C"),
                     "octave": {"f": fo.tolist(), "L": Lo.tolist()}, "third": {"f": f3.tolist(), "L": L3.tolist()},
                     "psd": {"f": f[1::step].tolist(), "db": psd_db.tolist()}}
    res["masker"]["LAeq_full_duration"] = la_full
    res["analysis_window_s"] = n_an / fs
    res["third_labels"] = [B.nominal_label(x) for x in res["target"]["third"]["f"]]
    res["octave_labels"] = [B.nominal_label(x) for x in res["target"]["octave"]["f"]]
    res["delta_LA"] = res["mix"]["LAeq"] - res["target"]["LAeq"]
    res["masker_to_target_LA"] = res["masker"]["LAeq"] - res["target"]["LAeq"]
    lt3 = np.array(res["target"]["third"]["L"])
    mtr = np.array(res["masker"]["third"]["L"]) - lt3
    # only bands where the machine has relevant energy (within 45 dB of its strongest band)
    mtr = np.where(lt3 >= lt3.max() - 45, mtr, np.nan)
    res["masker_to_target_third"] = [None if not np.isfinite(v) else float(v) for v in mtr]
    res["erb"] = {k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in est.items()
                  if k in ("bands_hz", "L_target", "L_masker", "threshold", "margin", "importance")}
    res["prominence_index_db"] = est["prominence_index_db"]
    res["audible_band_count"] = est["audible_band_count"]
    res["band_count"] = est["band_count"]
    res["worst_band_hz"] = est["worst_band_hz"]
    res["worst_margin_db"] = est["worst_margin_db"]
    res["assumptions"] = est["assumptions"] + [
        "Masker level evaluated per channel (average of L/R PSDs), i.e. headphone-equivalent at the listener",
        "Target spectrum " + ("measured" if meta["kind"] == "signal" else "from spectrum data (synthetic approximation for audio)"),
    ]
    if meta["kind"] == "signal":
        from .engine import select_channel, to_units
        x = to_units(meta, select_channel(meta, arrays["sig"]))
        fsx = meta["fs"]
        hop = int(0.5 * fsx)
        frames = []
        for i in range(0, max(1, len(x) - hop), hop)[:240]:
            seg_x = x[i:i + hop]
            if len(seg_x) < hop // 2:
                break
            fx, px = spectral.welch_psd(seg_x, fsx, 0.125)
            frames.append(np.interp(f, fx, px, right=0.0))
        if frames:
            tv = masking.time_varying(frames, pm, f, ref, cal, params, fs)
            res["time_varying"] = {"t": (np.arange(len(frames)) * 0.5).tolist(),
                                   "pi": tv["pi_frames"].tolist(), "median": tv["median"], "p90": tv["p90"], "max": tv["max"]}
    res["interpretation"] = interpret(res)
    return res


def interpret(res: dict) -> list:
    msgs = []
    pi = res["prominence_index_db"]
    if res["audible_band_count"] == 0:
        msgs.append("Model estimate: the target is below the estimated masked threshold (minus margin) in all relevant "
                    "auditory bands. Individual listeners may still detect it.")
    elif pi > 10:
        msgs.append(f"Model estimate: the target remains clearly above the estimated threshold (prominence index "
                    f"{pi:.1f} dB, worst band ≈ {res['worst_band_hz']:.0f} Hz). Expect partial masking at best.")
    else:
        msgs.append(f"Model estimate: partial masking — prominence index {pi:.1f} dB with {res['audible_band_count']} "
                    f"band(s) above the goal; the target is likely less prominent but still detectable.")
    msgs.append(f"Total A-weighted level changes by {res['delta_LA']:+.1f} dB when the soundscape is added "
                "(masking adds sound; it never reduces the machine's emission).")
    return msgs
