"""Exports: WAV (PCM16/24, float32), MATLAB .mat (v5, readable by `load`), CSV, JSON, HTML report."""
from __future__ import annotations

import csv
import datetime as dt
import html
import io
import json
import os

import numpy as np
import soundfile as sf
from scipy import io as sio

from ..acoustics import bands as B
from ..acoustics.levels import P0, a_weighting_db
from ..dsp import spectral
from ..engine import target_audio_block_source
from ..generation import PEAK_TARGET, load_masker

WAV_SUBTYPES = {"wav16": "PCM_16", "wav24": "PCM_24", "wav32f": "FLOAT"}
APP_VERSION = "0.1.0"


def stream_samples(project_dir, meta, arrays, info, stream: str):
    """Full-length stream in target units, (N, 2) float64 (target is duplicated to both channels)."""
    n = info["n"]
    masker = np.asarray(load_masker(project_dir)[:n], dtype=np.float64)
    if stream == "masker":
        return masker
    src, _ = target_audio_block_source(meta, arrays, info["fs"], info["seed"], info["duration_s"])
    tg = src(0, n)[:, None] * np.ones((1, 2))
    if stream == "target":
        return tg
    if stream == "mix":
        return tg + masker
    raise ValueError(stream)


def export(project_dir, meta, arrays, info, evaluation, opts: dict) -> list:
    """opts: formats [wav16|wav24|wav32f|mat|csv|json|report], stream masker|mix|target, channels 1|2,
    mat_signal_domain 'digital'|'pascal'. Returns list of written files with checks."""
    out_dir = os.path.join(project_dir, "exports")
    os.makedirs(out_dir, exist_ok=True)
    stream = opts.get("stream", "masker")
    channels = int(opts.get("channels", 2))
    fs = int(info["fs"])
    x = stream_samples(project_dir, meta, arrays, info, stream)
    if channels == 1:
        x = x.mean(axis=1, keepdims=True)
    # digital normalisation: one gain for the exported stream; when mix-preserving gain requested, use common gain
    if opts.get("preserve_relative_level", True):
        gain = info["preview_common_gain"]
    else:
        pk = float(np.max(np.abs(x))) or 1.0
        gain = PEAK_TARGET / pk
    xd = x * gain
    clipped = int(np.sum(np.abs(xd) > 1.0))
    xd = np.clip(xd, -1.0, 1.0)
    base = f"{opts.get('basename', 'naturemask')}_{stream}_{fs // 1000}k_{'mono' if channels == 1 else 'stereo'}"
    written = []
    cal = bool(meta["calibrated"])
    units_per_fs = (1.0 / gain)  # target units (Pa or FS) per digital full-scale unit
    for fmt in opts.get("formats", ["wav24"]):
        if fmt in WAV_SUBTYPES:
            p = os.path.join(out_dir, f"{base}_{fmt}.wav")
            sf.write(p, xd.astype(np.float32 if fmt == "wav32f" else np.float64), fs, subtype=WAV_SUBTYPES[fmt])
            chk = sf.info(p)
            back, _ = sf.read(p, always_2d=True)
            lsb = {"wav16": 2 ** -15, "wav24": 2 ** -23, "wav32f": 1e-7}[fmt]
            err = float(np.max(np.abs(back - xd)))
            written.append({"file": os.path.basename(p), "format": fmt, "samplerate": chk.samplerate,
                            "channels": chk.channels, "frames": chk.frames, "subtype": chk.subtype,
                            "max_roundtrip_error": err, "valid": bool(chk.samplerate == fs and chk.frames == len(xd)
                                                                      and chk.channels == channels and err <= lsb * 1.01),
                            "clipped_samples": clipped})
        elif fmt == "mat":
            p = os.path.join(out_dir, f"{base}.mat")
            written.append(write_mat(p, x, xd, fs, meta, info, evaluation, opts, cal, units_per_fs, stream))
        elif fmt == "csv":
            for name, rows in csv_tables(evaluation).items():
                p = os.path.join(out_dir, f"{opts.get('basename', 'naturemask')}_{name}.csv")
                with open(p, "w", newline="", encoding="utf-8") as fh:
                    csv.writer(fh).writerows(rows)
                written.append({"file": os.path.basename(p), "format": "csv", "valid": True})
        elif fmt == "json":
            p = os.path.join(out_dir, f"{opts.get('basename', 'naturemask')}_project.json")
            with open(p, "w", encoding="utf-8") as fh:
                json.dump({"app": "NatureMask Studio", "version": APP_VERSION, "target": meta, "render": info,
                           "evaluation": evaluation}, fh, indent=1, default=_json_default)
            written.append({"file": os.path.basename(p), "format": "json", "valid": True})
        elif fmt == "report":
            p = os.path.join(out_dir, f"{opts.get('basename', 'naturemask')}_report.html")
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(html_report(meta, info, evaluation))
            written.append({"file": os.path.basename(p), "format": "report", "valid": True})
    return written


def _json_default(o):
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    return str(o)


def _struct(d):
    """Convert a dict to something scipy.io.savemat writes as a MATLAB struct (nested ok)."""
    out = {}
    for k, v in d.items():
        key = "".join(c if c.isalnum() or c == "_" else "_" for c in str(k))[:63]
        if key and key[0].isdigit():
            key = "f_" + key
        if isinstance(v, dict):
            out[key] = _struct(v)
        elif v is None:
            out[key] = np.zeros((0, 0))
        elif isinstance(v, (list, tuple)):
            if all(isinstance(a, (int, float, np.floating, np.integer)) for a in v):
                out[key] = np.asarray(v, float)
            else:
                out[key] = json.dumps(v, default=_json_default)
        elif isinstance(v, bool):
            out[key] = bool(v)
        else:
            out[key] = v
    return out


def write_mat(path, x_units, x_digital, fs, meta, info, evaluation, opts, cal, units_per_fs, stream):
    domain_req = opts.get("mat_signal_domain", "digital")
    if domain_req == "pascal" and not cal:
        raise ValueError("Pressure (Pa) export needs a calibrated target; the design is uncalibrated.")
    sig = x_units if domain_req == "pascal" else x_digital
    n, c = sig.shape
    single = n * c > 60e6  # very long files: store single precision to stay well below MAT-v5 limits
    sig = sig.astype(np.float32 if single else np.float64)
    t = (np.arange(n, dtype=np.float64) / fs)[:, None]
    ref = 1.0
    data = {"sig": sig, "fs": float(fs), "t": t, "duration": n / fs, "channels": float(c)}
    # spectral analysis of the exported stream in physical / relative units (computed from x_units)
    mono_units = x_units.mean(axis=1)
    seg = mono_units[: min(n, fs * 120)]
    f, p = spectral.welch_psd(seg, fs, 0.5)
    if c == 2:
        f, pl = spectral.welch_psd(x_units[: len(seg), 0], fs, 0.5)
        _, pr = spectral.welch_psd(x_units[: len(seg), 1], fs, 0.5)
        p = 0.5 * (pl + pr)
    fo, Lo = B.band_levels_from_psd(f, p, P0 if cal else 1.0, 1, 31.5, 16000)
    f3, L3 = B.band_levels_from_psd(f, p, P0 if cal else 1.0, 3, 20, 20000)
    data["f_oct"] = fo[:, None]
    data["f_third"] = f3[:, None]
    data["f_psd"] = f[:, None]
    # Leq values are time integrals over the FULL exported signal (per-channel mean square), not PSD-based:
    # Welch's Hann segments under-weight segment edges and bias fluctuating sounds by ~0.2 dB (found via MATLAB check)
    from ..acoustics.levels import apply_weighting
    refl = P0 if cal else 1.0
    lz = 10 * np.log10(max(float(np.mean(x_units ** 2)), 1e-300) / refl ** 2)
    xa = apply_weighting(x_units, fs, "A")
    la = 10 * np.log10(max(float(np.mean(xa ** 2)), 1e-300) / refl ** 2)
    if cal:
        data.update({"L_Aeq": la, "L_Zeq": lz, "Lp_oct": Lo[:, None], "Lp_third": L3[:, None], "PSD": p[:, None]})
    else:  # never fabricate SPL: relative levels only, clearly named
        data.update({"Lrel_Aeq": la, "Lrel_Zeq": lz, "Lrel_oct": Lo[:, None], "Lrel_third": L3[:, None],
                     "PSD_rel": p[:, None]})
    md = {
        "app": "NatureMask Studio", "version": APP_VERSION,
        "created": dt.datetime.now().isoformat(timespec="seconds"),
        "stream": stream,
        "signal_domain": ("pressure_Pa" if domain_req == "pascal" else "digital_normalized"),
        "pa_per_full_scale": (units_per_fs if cal else None),
        "calibration_status": ("calibrated" if cal else "uncalibrated"),
        "calibration_note": ("Levels are design levels at the listener (dB re 20 uPa). Physical SPL requires calibrated playback."
                             if cal else "Uncalibrated: no SPL values exported; Lrel_* are relative dB re full scale."),
        "level_reference": ("20e-6 Pa" if cal else "1.0 (full scale of target recording units)"),
        "target_domain": meta["domain"], "target_provenance": meta["provenance"],
        "seed": info["seed"], "loop": info["loop"], "adaptive": info["adaptive"],
        "analysis_method": ("L_Aeq/L_Zeq: time-domain mean square over the full signal (A: linear-phase FIR from the "
                            "IEC 61672-1 analytic response); bands/PSD: Welch (Hann, 0.5 s, 50 %, first <=120 s), "
                            "ideal-edge integration at IEC 61260-1 base-10 mid-band frequencies"),
        "precision": "single" if single else "double",
        "components": [m["type"] for m in info["scene"].get("modules", []) if m.get("enabled", True)],
        "preset": info["scene"].get("preset"),
        "synthesis_config": json.dumps(info["scene"], default=_json_default),
        "optimization_solution": json.dumps(info.get("solution", {}), default=_json_default),
        "masking_estimate": {"prominence_index_db": evaluation.get("prominence_index_db"),
                             "delta_LA_db": evaluation.get("delta_LA"), "model": evaluation.get("model")},
    }
    data["metadata"] = _struct(md)
    sio.savemat(path, data, do_compression=True, long_field_names=True)
    back = sio.loadmat(path, squeeze_me=False)
    ok = back["sig"].shape == (n, c) and float(back["fs"].ravel()[0]) == fs and back["t"].shape == (n, 1)
    return {"file": os.path.basename(path), "format": "mat", "valid": bool(ok), "variables": sorted(k for k in back if not k.startswith("__")),
            "signal_domain": md["signal_domain"], "precision": md["precision"]}


def csv_tables(ev: dict) -> dict:
    rows3 = [["f_center_hz", "label", "target_dB", "masker_dB", "mix_dB", "masker_minus_target_dB", "A_weight_dB"]]
    for i, f in enumerate(ev["target"]["third"]["f"]):
        rows3.append([round(f, 2), ev["third_labels"][i], round(ev["target"]["third"]["L"][i], 2),
                      round(ev["masker"]["third"]["L"][i], 2), round(ev["mix"]["third"]["L"][i], 2),
                      "" if ev["masker_to_target_third"][i] is None else round(ev["masker_to_target_third"][i], 2),
                      round(float(a_weighting_db(f)), 2)])
    rowso = [["f_center_hz", "label", "target_dB", "masker_dB", "mix_dB"]]
    for i, f in enumerate(ev["target"]["octave"]["f"]):
        rowso.append([round(f, 2), ev["octave_labels"][i], round(ev["target"]["octave"]["L"][i], 2),
                      round(ev["masker"]["octave"]["L"][i], 2), round(ev["mix"]["octave"]["L"][i], 2)])
    rowsp = [["f_hz", "target_dB_per_Hz", "masker_dB_per_Hz", "mix_dB_per_Hz"]]
    for i, f in enumerate(ev["target"]["psd"]["f"]):
        rowsp.append([round(f, 2), round(ev["target"]["psd"]["db"][i], 2), round(ev["masker"]["psd"]["db"][i], 2),
                      round(ev["mix"]["psd"]["db"][i], 2)])
    rowse = [["erb_band_hz", "target_dB", "masker_dB", "masked_threshold_dB", "margin_dB"]]
    e = ev["erb"]
    for i, f in enumerate(e["bands_hz"]):
        rowse.append([round(f, 1), round(e["L_target"][i], 2), round(e["L_masker"][i], 2), round(e["threshold"][i], 2),
                      round(e["margin"][i], 2)])
    unit = ev["level_unit"]
    for r in (rows3, rowso, rowsp, rowse):
        r.insert(0, [f"# levels: {unit}"])
    return {"third_octave": rows3, "octave": rowso, "spectrum": rowsp, "masking_erb": rowse}


def html_report(meta, info, ev) -> str:
    esc = html.escape
    lvl = ev["level_unit"]
    rows = "".join(
        f"<tr><td>{esc(ev['octave_labels'][i])}</td><td>{ev['target']['octave']['L'][i]:.1f}</td>"
        f"<td>{ev['masker']['octave']['L'][i]:.1f}</td><td>{ev['mix']['octave']['L'][i]:.1f}</td></tr>"
        for i in range(len(ev["octave_labels"])))
    interp = "".join(f"<li>{esc(m)}</li>" for m in ev.get("interpretation", []))
    assumptions = "".join(f"<li>{esc(a)}</li>" for a in ev.get("assumptions", []))
    mods = ", ".join(m["type"] for m in info["scene"].get("modules", []) if m.get("enabled", True))
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>NatureMask Studio report</title>
<style>body{{font:15px/1.5 system-ui,Segoe UI,sans-serif;max-width:860px;margin:32px auto;padding:0 16px;color:#1d2420}}
h1{{font-size:26px}}h2{{font-size:18px;margin-top:28px;border-bottom:1px solid #ccd5cf}}table{{border-collapse:collapse;width:100%}}
td,th{{border-bottom:1px solid #e3e8e4;padding:6px 8px;text-align:right}}td:first-child,th:first-child{{text-align:left}}
.note{{background:#f2f6f3;border:1px solid #d5e0d8;padding:12px 14px;border-radius:6px}}</style></head><body>
<h1>NatureMask Studio — Masking report</h1>
<p>Generated {dt.datetime.now().isoformat(timespec='seconds')} · app {APP_VERSION}</p>
<div class="note"><b>Important.</b> Masking adds sound; it does not reduce the machine's sound power or level. Results are
engineering estimates (model: {esc(ev['model'])}) and are not validated by listening tests. Do not use masking to hide alarms,
warnings or safety-relevant speech. Physical SPL requires calibrated playback.</div>
<h2>Target</h2><p>Domain: {esc(meta['domain'])} · provenance: {esc(meta['provenance'])} · calibrated: {meta['calibrated']}</p>
<h2>Soundscape</h2><p>Preset: {esc(str(info['scene'].get('name')))} · modules: {esc(mods)} · seed {info['seed']} ·
{info['duration_s']:.0f} s at {info['fs']} Hz · loop: {info['loop']} · adaptive: {info['adaptive']}</p>
<h2>Levels ({esc(lvl)})</h2><table><tr><th></th><th>L<sub>Aeq</sub></th><th>L<sub>Zeq</sub></th><th>L<sub>Ceq</sub></th></tr>
<tr><td>Target</td><td>{ev['target']['LAeq']:.1f}</td><td>{ev['target']['LZeq']:.1f}</td><td>{ev['target']['LCeq']:.1f}</td></tr>
<tr><td>Soundscape</td><td>{ev['masker']['LAeq']:.1f}</td><td>{ev['masker']['LZeq']:.1f}</td><td>{ev['masker']['LCeq']:.1f}</td></tr>
<tr><td>Combined</td><td>{ev['mix']['LAeq']:.1f}</td><td>{ev['mix']['LZeq']:.1f}</td><td>{ev['mix']['LCeq']:.1f}</td></tr></table>
<p>Change in A-weighted level: {ev['delta_LA']:+.1f} dB · masker-to-target (A): {ev['masker_to_target_LA']:+.1f} dB</p>
<h2>Masking estimate</h2><p>Prominence index: {ev['prominence_index_db']:.1f} dB (0 dB ≈ at estimated threshold in one band; a model
index, not a probability) · bands above goal: {ev['audible_band_count']} of {ev['band_count']}</p><ul>{interp}</ul>
<h2>Octave bands ({esc(lvl)})</h2><table><tr><th>Band (Hz)</th><th>Target</th><th>Soundscape</th><th>Combined</th></tr>{rows}</table>
<h2>Assumptions</h2><ul>{assumptions}</ul></body></html>"""
