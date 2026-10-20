"""Sound levels, frequency weightings (IEC 61672-1 analytic forms) and time weighting.

Conventions: pressure in Pa when calibrated; otherwise digital full-scale units with reference 1.0
(levels are then relative, dBFS). See skill: algorithms/spl-and-weighting.md.
"""
from __future__ import annotations

import math

import numpy as np
from scipy import signal

P0 = 20e-6  # Pa

_F1, _F2, _F3, _F4 = 20.598997, 107.65265, 737.86223, 12194.217
_A1000 = -2.000
_C1000 = -0.062


def ref_for(calibrated: bool) -> float:
    return P0 if calibrated else 1.0


def level_from_ms(ms, ref: float = P0):
    """10 log10(mean-square / ref^2); -inf safe."""
    ms = np.asarray(ms, float)
    with np.errstate(divide="ignore"):
        return 10.0 * np.log10(np.maximum(ms, 1e-300) / ref ** 2)


def spl(x, ref: float = P0) -> float:
    x = np.asarray(x, float)
    return float(level_from_ms(np.mean(x ** 2), ref))


def energy_sum(levels_db) -> float:
    l = np.asarray(levels_db, float)
    l = l[np.isfinite(l)]
    if l.size == 0:
        return -math.inf
    return float(10.0 * np.log10(np.sum(10.0 ** (l / 10.0))))


def energy_difference(total_db: float, part_db: float) -> float:
    """Level of the remainder when `part` is removed from `total` (incoherent)."""
    d = 10 ** (total_db / 10) - 10 ** (part_db / 10)
    return 10 * math.log10(d) if d > 0 else -math.inf


def a_weighting_db(f):
    f = np.asarray(f, float)
    f2 = f ** 2
    ra = (_F4 ** 2 * f2 ** 2) / ((f2 + _F1 ** 2) * np.sqrt((f2 + _F2 ** 2) * (f2 + _F3 ** 2)) * (f2 + _F4 ** 2))
    with np.errstate(divide="ignore"):
        return 20.0 * np.log10(np.maximum(ra, 1e-300)) - _A1000


def c_weighting_db(f):
    f = np.asarray(f, float)
    f2 = f ** 2
    rc = (_F4 ** 2 * f2) / ((f2 + _F1 ** 2) * (f2 + _F4 ** 2))
    with np.errstate(divide="ignore"):
        return 20.0 * np.log10(np.maximum(rc, 1e-300)) - _C1000


def weighting_db(f, kind: str):
    kind = kind.upper()
    if kind == "A":
        return a_weighting_db(f)
    if kind == "C":
        return c_weighting_db(f)
    if kind == "Z":
        return np.zeros_like(np.asarray(f, float))
    raise ValueError(f"unknown weighting {kind}")


def weighting_sos(kind: str, fs: float):
    """Digital A/C weighting filter (bilinear transform of the IEC analog prototype), unity at 1 kHz."""
    kind = kind.upper()
    w = [2 * np.pi * f for f in (_F1, _F2, _F3, _F4)]
    if kind == "A":
        z = [0, 0, 0, 0]
        p = [-w[0], -w[0], -w[1], -w[2], -w[3], -w[3]]
    elif kind == "C":
        z = [0, 0]
        p = [-w[0], -w[0], -w[3], -w[3]]
    else:
        raise ValueError(kind)
    zd, pd, kd = signal.bilinear_zpk(z, p, 1.0, fs)
    sos = signal.zpk2sos(zd, pd, kd)
    _, h = signal.sosfreqz(sos, worN=[1000.0], fs=fs)
    sos[0, :3] /= abs(h[0])
    return sos


_FIR_CACHE: dict = {}


def weighting_fir(kind: str, fs: float, numtaps: int = 16383):
    """Linear-phase FIR approximating the exact analytic |W(f)| (frequency sampling, firwin2).

    Preferred over the bilinear IIR: plain bilinear transform of the IEC prototype errs by ~1.2 dB at
    10 kHz for fs = 48 kHz (frequency warping of the 12.2 kHz poles)."""
    key = (kind.upper(), float(fs), numtaps)
    if key not in _FIR_CACHE:
        f = np.concatenate([[0.0], np.geomspace(5.0, fs / 2 * 0.999, 2000), [fs / 2]])
        g = 10 ** (weighting_db(np.maximum(f, 1e-3), kind) / 20)
        g[0] = 0.0
        g[-1] = g[-2]
        _FIR_CACHE[key] = signal.firwin2(numtaps, f, g, fs=fs, window="blackmanharris")
    return _FIR_CACHE[key]


def apply_weighting(x, fs: float, kind: str):
    """Frequency-weight a signal (time-aligned: the FIR group delay is removed)."""
    x = np.asarray(x, float)
    if kind.upper() == "Z":
        return x
    h = weighting_fir(kind, fs)
    d = (len(h) - 1) // 2
    if x.ndim == 1:
        y = signal.oaconvolve(x, h, mode="full")
    else:
        y = signal.oaconvolve(x, h[:, None], mode="full", axes=0)
    return y[d:d + len(x)]


def time_weighted_ms(x, fs: float, tau: float = 0.125, step_s: float = 0.01):
    """Exponential time weighting of x^2 (F: 0.125 s, S: 1 s); returns (t, mean-square) sampled every step_s."""
    x = np.asarray(x, float)
    a = math.exp(-1.0 / (tau * fs))
    y = signal.lfilter([1 - a], [1, -a], x ** 2)
    hop = max(1, int(round(step_s * fs)))
    idx = np.arange(hop - 1, len(y), hop)
    return idx / fs, y[idx]


def level_statistics(x, fs: float, ref: float, weighting: str = "A") -> dict:
    """Leq, Fast max, percentile levels and level time history (weighted)."""
    xw = apply_weighting(x, fs, weighting)
    leq = spl(xw, ref)
    t, ms = time_weighted_ms(xw, fs, 0.125)
    lf = level_from_ms(ms, ref)
    # discard the first 0.5 s (filter settling of exponential averager)
    keep = t >= min(0.5, t[-1] / 2) if len(t) else slice(None)
    lfk = lf[keep] if len(t) else lf
    out = {"Leq": leq, "Lmax_F": float(np.max(lfk)) if lfk.size else leq,
           "L10": float(np.percentile(lfk, 90)) if lfk.size else leq,
           "L50": float(np.percentile(lfk, 50)) if lfk.size else leq,
           "L90": float(np.percentile(lfk, 10)) if lfk.size else leq,
           "t": t, "LF": lf}
    return out
