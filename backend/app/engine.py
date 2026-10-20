"""Domain logic tying together import, analysis, optimization, generation and evaluation.

Targets are stored as plain dicts (JSON-able metadata) plus numpy arrays (signal or spectrum).
Every target has `domain` and `provenance`; every level carries its unit.
"""
from __future__ import annotations

import math

import numpy as np
from scipy import signal as sps

from .acoustics import bands as B
from .acoustics.levels import P0, a_weighting_db, c_weighting_db, energy_sum, level_statistics
from .acoustics.propagation import lw_to_lp
from .dsp import spectral
from .psychoacoustics import masking
from .synthesis.target_synth import SYNTH_LABEL, SpectrumTarget, demo_machine_spectrum

ANALYSIS_SEG_S = 0.5

MACHINE_TEMPLATES = {
    # relative third-octave shape: peak frequency (Hz), width (octaves), extra tones (Hz, dB rel peak)
    "electric_drill": {"label": "Electric drill", "peak_hz": 2500, "width_oct": 1.6, "tones": [(2400, 2), (4800, -8)]},
    "circular_saw": {"label": "Circular saw", "peak_hz": 3150, "width_oct": 1.8, "tones": [(3000, 4)]},
    "angle_grinder": {"label": "Angle grinder", "peak_hz": 5000, "width_oct": 1.6, "tones": [(6300, 3)]},
    "hammer_drill": {"label": "Hammer drill", "peak_hz": 2000, "width_oct": 2.2, "tones": []},
    "air_compressor": {"label": "Air compressor", "peak_hz": 500, "width_oct": 2.2, "tones": [(100, 0)]},
    "generator": {"label": "Generator", "peak_hz": 125, "width_oct": 1.8, "tones": [(100, 3), (150, -3)]},
    "electric_motor": {"label": "Electric motor", "peak_hz": 1000, "width_oct": 2.0, "tones": [(100, -2), (1200, 0)]},
    "fan": {"label": "Fan", "peak_hz": 315, "width_oct": 2.0, "tones": [(240, 1)]},
    "pump": {"label": "Pump", "peak_hz": 250, "width_oct": 2.0, "tones": [(50, -4), (100, -2)]},
    "broadband": {"label": "Generic broadband (pink-like)", "peak_hz": 1000, "width_oct": 6.0, "tones": []},
}


def analysis_grid(fs: float, seg_s: float = ANALYSIS_SEG_S):
    n = int(2 ** round(math.log2(seg_s * fs)))
    return np.linspace(0, fs / 2, n // 2 + 1)


def template_spectrum(template: str, la_db: float, fmin=25, fmax=16000):
    """ESTIMATE: third-octave Lp spectrum with a template shape scaled to a given overall L_A."""
    t = MACHINE_TEMPLATES[template]
    fm, _, _ = B.band_centres(3, fmin, fmax)
    rel = -6.0 * (np.log2(fm / t["peak_hz"]) / (t["width_oct"] / 2)) ** 2 / 2
    tones = [{"f": f, "rel_db": r} for f, r in t["tones"]]
    la_rel = energy_sum(rel + a_weighting_db(fm))
    tone_la = energy_sum([r + float(a_weighting_db(f)) for f, r in t["tones"]]) if t["tones"] else -math.inf
    total = energy_sum([la_rel, tone_la]) if t["tones"] else la_rel
    off = la_db - total
    return fm, rel + off, [{"f": tn["f"], "level_db": tn["rel_db"] + off} for tn in tones]


# ----------------------------------------------------------------------------- target construction

def target_from_signal(sig, fs, domain: str, k_pa_per_unit: float | None = None, channel: int | None = 0,
                       name="Recording", meta=None, reference_la: float | None = None):
    sig = np.asarray(sig, float)
    if sig.ndim == 1:
        sig = sig[:, None]
    if domain not in ("PASCAL", "DIGITAL_CALIBRATED", "DIGITAL_UNCALIBRATED"):
        raise ValueError("domain must be PASCAL, DIGITAL_CALIBRATED or DIGITAL_UNCALIBRATED")
    cal = {"method": None}
    if domain == "DIGITAL_CALIBRATED":
        if reference_la is not None:
            x = sig[:, channel or 0] if channel is not None else sig.mean(1)
            from .acoustics.levels import apply_weighting, spl
            la_fs = spl(apply_weighting(x, fs, "A"), 1.0)
            k_pa_per_unit = 10 ** ((reference_la - la_fs) / 20) * P0
            cal = {"method": "REFERENCE_LEVEL", "reference_LA": reference_la}
        if not k_pa_per_unit or k_pa_per_unit <= 0:
            raise ValueError("calibration factor k (Pa per unit) required for DIGITAL_CALIBRATED")
        cal["method"] = cal["method"] or "FACTOR"
        cal["k_pa_per_unit"] = float(k_pa_per_unit)
    return {"kind": "signal", "name": name, "domain": domain, "provenance": "MEASURED",
            "calibrated": domain != "DIGITAL_UNCALIBRATED", "calibration": cal, "fs": float(fs),
            "channels": int(sig.shape[1]), "channel": channel, "duration_s": sig.shape[0] / fs,
            "meta": meta or {}}, {"sig": sig}


def target_from_spectrum(f, L, representation: str, quantity: str = "Lp", distance_m: float | None = None,
                         field: str = "hemispherical", directivity_db: float = 0.0, air_absorption: bool = False,
                         tones=None, pattern="stationary", name="Spectrum", provenance="MEASURED", a_weighted=False,
                         notes=None):
    from .io.importers import snap_to_exact
    f = np.asarray(f, float)
    L = np.asarray(L, float)
    rep = representation
    if rep in ("octave", "third"):
        f = snap_to_exact(f)
    if a_weighted:
        L = L - a_weighting_db(f)
    meta = {"input_quantity": quantity, "notes": notes or []}
    if quantity == "Lw":
        if not distance_m:
            raise ValueError("A listener distance is required to convert sound power (Lw) to sound pressure (Lp).")
        L, info = lw_to_lp(f, L, distance_m, field, directivity_db, air_absorption)
        meta["lw_conversion"] = info
        provenance = "ESTIMATED_FROM_LW"
    tones = [dict(t) for t in (tones or [])]
    return {"kind": "spectrum", "name": name, "domain": "SPECTRUM_ONLY", "calibrated": True,
            "provenance": provenance, "representation": rep, "pattern": pattern, "tones": tones,
            "listener_distance_m": distance_m, "meta": meta}, {"f": f, "L": L}


# ----------------------------------------------------------------------------- analysis

def target_psd(meta: dict, arrays: dict, fs_out: int = 48000):
    """One-sided PSD of the target at the listener in target units (Pa^2/Hz if calibrated else FS^2/Hz)."""
    if meta["kind"] == "signal":
        x = select_channel(meta, arrays["sig"])
        fs = meta["fs"]
        f, p = spectral.welch_psd(x, fs, ANALYSIS_SEG_S)
        if fs != fs_out:  # express on the output grid (zero above input Nyquist)
            fg = analysis_grid(fs_out)
            p = np.interp(fg, f, p, right=0.0)
            f = fg
        return f, p
    f_grid = analysis_grid(fs_out)
    b = 1 if meta["representation"] == "octave" else 3
    fL, L = arrays["f"], arrays["L"]
    if meta["representation"] == "continuous":
        # values are spectrum levels? We treat continuous curves as narrowband levels per 1 Hz (dB re 20 uPa/sqrt(Hz))
        d = np.interp(np.log10(np.maximum(f_grid, 1)), np.log10(fL), L, left=L[0] - 30, right=L[-1] - 30)
        psd = P0 ** 2 * 10 ** (d / 10)
    else:
        psd = B.psd_from_bands(fL, L, P0, f_grid, b)
    # tones: remove their energy from broadband (keeping band totals) and add as narrow lines
    df = f_grid[1] - f_grid[0]
    for t in meta.get("tones", []):
        i = int(np.argmin(abs(f_grid - t["f"])))
        pt = P0 ** 2 * 10 ** (t["level_db"] / 10)
        lo, hi = t["f"] * B.G10 ** (-1 / (2 * b)), t["f"] * B.G10 ** (1 / (2 * b))
        m = (f_grid >= lo) & (f_grid <= hi)
        band_p = np.sum(psd[m]) * df
        if band_p > pt:
            psd[m] *= (band_p - pt) / band_p
        psd[i] += pt / df
    return f_grid, psd


def select_channel(meta, sig):
    ch = meta.get("channel")
    if ch is None or ch == "mean":
        return sig.mean(axis=1)
    return sig[:, int(ch)]


def to_units(meta, x):
    """Convert stored signal samples to target units (Pa if calibrated, else FS)."""
    if meta.get("domain") == "DIGITAL_CALIBRATED":
        return x * meta["calibration"]["k_pa_per_unit"]
    return x


def analyze_target(meta, arrays, fs_out=48000):
    cal = bool(meta["calibrated"])
    ref = P0 if cal else 1.0
    unit = "dB re 20 µPa" if cal else "dB re full scale (relative, uncalibrated)"
    out = {"domain": meta["domain"], "provenance": meta["provenance"], "calibrated": cal, "level_unit": unit}
    if meta["kind"] == "signal":
        x = to_units(meta, select_channel(meta, arrays["sig"]))
        fs = meta["fs"]
        st = level_statistics(x, fs, ref, "A")
        stz = level_statistics(x, fs, ref, "Z")
        stc = level_statistics(x, fs, ref, "C")
        f, p = spectral.welch_psd(x, fs, ANALYSIS_SEG_S)
        tt, ll = spectral.short_time_levels(x, fs, ref, 0.125)
        out["temporal"] = spectral.temporal_character(ll)
        out["levels"] = {"LAeq": st["Leq"], "LZeq": stz["Leq"], "LCeq": stc["Leq"], "LAFmax": st["Lmax_F"],
                         "LA10": st["L10"], "LA50": st["L50"], "LA90": st["L90"]}
        step = max(1, len(st["t"]) // 1500)
        out["level_history"] = {"t": st["t"][::step].tolist(), "LAF": st["LF"][::step].tolist()}
        n = len(x)
        px = 1200
        w = max(1, n // px)
        seg = x[: (n // w) * w].reshape(-1, w)
        out["waveform"] = {"t": (np.arange(seg.shape[0]) * w / fs).tolist(), "min": seg.min(1).tolist(),
                           "max": seg.max(1).tolist(), "unit": "Pa" if cal else "FS"}
        sf, stt, sdb = spectral.spectrogram_db(x, fs, ref, fmax=min(16000, fs / 2))
        fi = np.unique(np.round(np.geomspace(1, len(sf) - 1, 160)).astype(int))
        out["spectrogram"] = {"f": sf[fi].tolist(), "t": stt.tolist(), "db": sdb[fi].T.round(1).tolist()}
        out["duration_s"] = n / fs
    else:
        f, p = target_psd(meta, arrays, fs_out)
        fm = arrays["f"]
        L = arrays["L"]
        b = 1 if meta["representation"] == "octave" else 3
        tone_e = [t["level_db"] for t in meta.get("tones", [])]
        lz = B.total_from_psd(f, p, ref, "Z")
        out["levels"] = {"LAeq": B.total_from_psd(f, p, ref, "A"), "LZeq": lz, "LCeq": B.total_from_psd(f, p, ref, "C")}
        out["temporal"] = {"class": meta.get("pattern", "stationary"), "note": "declared by user (no recording)"}
        out["synthetic_note"] = SYNTH_LABEL
    fo, Lo = B.band_levels_from_psd(f, p, ref, 1, 31.5, min(16000, f[-1] / 1.42))
    ft, Lt = B.band_levels_from_psd(f, p, ref, 3, 20, min(20000, f[-1] / 1.13))
    out["octave"] = {"f": fo.tolist(), "labels": [B.nominal_label(x) for x in fo], "L": Lo.tolist(),
                     "LA": (Lo + a_weighting_db(fo)).tolist()}
    out["third"] = {"f": ft.tolist(), "labels": [B.nominal_label(x) for x in ft], "L": Lt.tolist(),
                    "LA": (Lt + a_weighting_db(ft)).tolist()}
    step = max(1, len(f) // 2000)
    with np.errstate(divide="ignore"):
        out["psd"] = {"f": f[1::step].tolist(), "db": (10 * np.log10(np.maximum(p[1::step], 1e-300) / ref ** 2)).tolist(),
                      "unit": ("dB re (20 µPa)²/Hz" if cal else "dB re FS²/Hz")}
    if meta["kind"] == "signal":
        tones = spectral.find_tones(f, p, ref)
    else:
        tones = [{"frequency_hz": t["f"], "level_db": t["level_db"], "prominent": True, "declared": True}
                 for t in meta.get("tones", [])]
    out["tones"] = tones
    # dominant bands (A-weighted thirds within 6 dB of max)
    la3 = np.array(out["third"]["LA"])
    dom = [out["third"]["labels"][i] for i in np.argsort(-la3)[:5] if la3[i] > la3.max() - 6]
    out["dominant_bands"] = dom
    out["difficulty"] = masking_difficulty(ft, Lt, tones, out["temporal"].get("class", "stationary"))
    return out


def masking_difficulty(ft, Lt, tones, temporal_class):
    """Qualitative heuristic (documented): share of A-weighted energy < 160 Hz, prominent tones, intermittency."""
    la = np.asarray(Lt) + a_weighting_db(ft)
    e = 10 ** (la / 10)
    lf_share = float(e[np.asarray(ft) < 160].sum() / max(e.sum(), 1e-300))
    lz = 10 ** (np.asarray(Lt) / 10)
    lf_share_z = float(lz[np.asarray(ft) < 160].sum() / max(lz.sum(), 1e-300))
    prom = [t for t in tones if t.get("prominent")]
    score = 0
    reasons = []
    if lf_share_z > 0.5:
        score += 2
        reasons.append(f"{lf_share_z*100:.0f} % of unweighted energy below 160 Hz — natural sounds rarely cover this range")
    elif lf_share > 0.15:
        score += 1
        reasons.append("significant low-frequency content")
    if prom:
        score += 1 if len(prom) < 3 else 2
        reasons.append(f"{len(prom)} prominent tonal component(s) — tones need narrowband masker energy")
    if temporal_class == "intermittent":
        score += 1
        reasons.append("intermittent operation — peaks exceed a steady masker; onsets stay noticeable")
    level = "low" if score <= 1 else ("medium" if score <= 3 else "high")
    return {"level": level, "score": score, "reasons": reasons or ["broadband, steady, mid/high-frequency target"],
            "method": "heuristic indicator (not a psychoacoustic metric)"}


# ----------------------------------------------------------------------------- target audio for preview

def target_audio_block_source(meta, arrays, fs_out: int, seed: int, duration_s: float):
    """Callable (start, n) -> mono target samples in target units at fs_out."""
    if meta["kind"] == "signal":
        x = to_units(meta, select_channel(meta, arrays["sig"]))
        fs = meta["fs"]
        if int(fs) != fs_out:
            from fractions import Fraction
            fr = Fraction(fs_out, int(fs)).limit_denominator(1000)
            x = sps.resample_poly(x, fr.numerator, fr.denominator)
        n = len(x)

        def src(start, m):
            idx = (start + np.arange(m)) % n  # loops if shorter than the soundscape (reported)
            return x[idx]
        return src, {"looped": n < duration_s * fs_out, "label": "recording"}
    f, p = target_psd(meta, arrays, fs_out)
    # broadband part only (tones rendered as sinusoids for clean lines)
    pb = p.copy()
    df = f[1] - f[0]
    tones = []
    for t in meta.get("tones", []):
        i = int(np.argmin(abs(f - t["f"])))
        pt = P0 ** 2 * 10 ** (t["level_db"] / 10)
        pb[i] = max(pb[i] - pt / df, 0)
        tones.append({"f": t["f"], "rms": math.sqrt(pt)})
    mod = SpectrumTarget(fs_out, seed, {"f": f, "psd": pb, "tones": tones, "pattern": meta.get("pattern", "stationary")},
                         duration_s + 5)

    def src(start, m):
        return mod.render(start, m)[:, 0]
    return src, {"looped": False, "label": SYNTH_LABEL}
