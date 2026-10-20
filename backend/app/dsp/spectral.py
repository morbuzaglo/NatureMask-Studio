"""Spectral analysis: Welch PSD, spectrogram, tonal-component screening, temporal statistics."""
from __future__ import annotations

import math

import numpy as np
from scipy import signal

from ..acoustics.levels import level_from_ms


def welch_psd(x, fs: float, seg_s: float = 0.5, overlap: float = 0.5):
    """One-sided PSD (units^2/Hz), Hann window. Parseval: sum(psd)*df == var(x)."""
    x = np.asarray(x, float)
    nper = int(2 ** round(math.log2(max(seg_s * fs, 64))))
    nper = min(nper, len(x))
    f, p = signal.welch(x, fs, window="hann", nperseg=nper, noverlap=int(nper * overlap),
                        scaling="density", detrend=False)
    return f, p


def spectrogram_db(x, fs: float, ref: float, seg_s: float = 0.046, max_frames: int = 600, fmax: float | None = None):
    """Spectrogram in dB re ref^2/Hz, decimated in time to at most max_frames columns for display."""
    x = np.asarray(x, float)
    nper = int(2 ** round(math.log2(seg_s * fs)))
    hop = max(nper // 2, int(len(x) / max_frames))
    f, t, s = signal.spectrogram(x, fs, window="hann", nperseg=nper, noverlap=max(0, nper - hop),
                                 scaling="density", mode="psd")
    if fmax:
        m = f <= fmax
        f, s = f[m], s[m]
    with np.errstate(divide="ignore"):
        db = 10 * np.log10(np.maximum(s, 1e-300) / ref ** 2)
    return f, t, db


def critical_band_hz(f):
    f = np.asarray(f, float)
    return 25.0 + 75.0 * (1.0 + 1.4 * (f / 1000.0) ** 2) ** 0.69


def tnr_criterion_db(f):
    f = np.asarray(f, float)
    return np.where(f >= 1000, 8.0, 8.0 + 8.33 * np.log10(1000.0 / np.maximum(f, 1)))


def pr_criterion_db(f):
    f = np.asarray(f, float)
    return np.where(f >= 1000, 9.0, 9.0 + 10.0 * np.log10(1000.0 / np.maximum(f, 1)))


def find_tones(f, psd, ref: float, fmin: float = 50.0, fmax: float = 12000.0, max_tones: int = 12,
               min_prominence_db: float = 6.0):
    """Screen tonal components (ECMA-418-1 / ANSI S1.13 style TNR & PR). Engineering screening only.

    Returns list of dicts sorted by TNR: frequency, level (dB), TNR, PR, criteria and 'prominent'.
    """
    f = np.asarray(f, float)
    psd = np.asarray(psd, float)
    df = f[1] - f[0]
    db = 10 * np.log10(np.maximum(psd, 1e-300))
    # local background: median in a sliding window of ~1/3 critical band
    peaks, props = signal.find_peaks(db, prominence=min_prominence_db)
    out = []
    for p in peaks:
        fc = f[p]
        if fc < fmin or fc > fmax:
            continue
        cb = float(critical_band_hz(fc))
        lo, hi = fc - cb / 2, fc + cb / 2
        band = (f >= lo) & (f <= hi)
        # tone power: main lobe +-2 bins (Hann main lobe width = 4 bins)
        lobe = (f >= fc - 2.5 * df) & (f <= fc + 2.5 * df)
        pt = float(np.sum(psd[lobe]) * df)
        pn_total = float(np.sum(psd[band & ~lobe]) * df)
        n_bins_noise = int(np.sum(band & ~lobe))
        n_bins_band = int(np.sum(band))
        if n_bins_noise <= 0 or pn_total <= 0:
            continue
        pn = pn_total * n_bins_band / n_bins_noise  # noise power extrapolated to the full critical band
        tnr = 10 * math.log10(pt / pn)
        # prominence ratio: critical band around tone vs mean of adjacent bands
        def band_pow(c):
            w = float(critical_band_hz(c))
            m = (f >= c - w / 2) & (f <= c + w / 2)
            return float(np.sum(psd[m]) * df)
        pm = band_pow(fc)
        pl = band_pow(max(fc - cb, f[1]))
        pu = band_pow(fc + cb)
        pr = 10 * math.log10(pm / max(0.5 * (pl + pu), 1e-300))
        tc, pc = float(tnr_criterion_db(fc)), float(pr_criterion_db(fc))
        out.append({"frequency_hz": float(fc), "level_db": float(10 * math.log10(max(pt, 1e-300) / ref ** 2)),
                    "tnr_db": tnr, "pr_db": pr, "tnr_criterion_db": tc, "pr_criterion_db": pc,
                    "prominent": bool(tnr >= tc or pr >= pc)})
    out.sort(key=lambda d: -d["tnr_db"])
    # suppress duplicates within half a critical band
    sel = []
    for d in out:
        if all(abs(d["frequency_hz"] - s["frequency_hz"]) > critical_band_hz(d["frequency_hz"]) / 2 for s in sel):
            sel.append(d)
        if len(sel) >= max_tones:
            break
    return sel


def short_time_levels(x, fs: float, ref: float, frame_s: float = 0.125):
    x = np.asarray(x, float)
    n = int(frame_s * fs)
    m = len(x) // n
    if m == 0:
        return np.array([0.0]), np.array([float(level_from_ms(np.mean(x ** 2), ref))])
    ms = np.mean(x[: m * n].reshape(m, n) ** 2, axis=1)
    return (np.arange(m) + 0.5) * frame_s, level_from_ms(ms, ref)


def temporal_character(levels_db) -> dict:
    """Classify stationarity from short-time level statistics (heuristic thresholds, documented)."""
    l = np.asarray(levels_db, float)
    l = l[np.isfinite(l)]
    if l.size < 4:
        return {"class": "unknown"}
    l10, l50, l90 = np.percentile(l, 90), np.percentile(l, 50), np.percentile(l, 10)
    spread = float(l10 - l90)
    # fraction of frames within 10 dB of the max: "on" fraction for intermittent sources
    on = float(np.mean(l > (l.max() - 10)))
    if spread < 3:
        cls = "stationary"
    elif on < 0.6 and spread > 10:
        cls = "intermittent"
    else:
        cls = "time-varying"
    return {"class": cls, "L10_minus_L90_db": spread, "on_fraction": on, "L10": float(l10),
            "L50": float(l50), "L90": float(l90),
            "rule": "stationary if L10-L90<3 dB; intermittent if >10 dB and on-fraction<0.6 (heuristic)"}
