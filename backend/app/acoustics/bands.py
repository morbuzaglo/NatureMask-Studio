"""Fractional-octave bands (IEC 61260-1 base-10) and spectrum representation conversions.

PSD (power/Hz), band levels and FFT-bin levels are different quantities; this module is the only
place that converts between them. See skill: algorithms/octave-bands.md.
"""
from __future__ import annotations

import numpy as np

from .levels import a_weighting_db, energy_sum, weighting_db

G10 = 10 ** 0.3
NOMINAL_THIRD = [10, 12.5, 16, 20, 25, 31.5, 40, 50, 63, 80, 100, 125, 160, 200, 250, 315, 400, 500, 630, 800,
                 1000, 1250, 1600, 2000, 2500, 3150, 4000, 5000, 6300, 8000, 10000, 12500, 16000, 20000]


def band_index_range(b: int, fmin: float, fmax: float):
    xs = np.arange(-60 * b // 3 - 3, 60 * b // 3 + 4)
    fm = 1000.0 * G10 ** (xs / b)
    keep = (fm >= fmin * G10 ** (-1 / (2 * b))) & (fm <= fmax * G10 ** (1 / (2 * b)))
    return xs[keep]


def band_centres(b: int = 3, fmin: float = 20.0, fmax: float = 20000.0):
    """Exact mid-band frequencies and edges for b = 1 (octave) or 3 (third-octave)."""
    if b not in (1, 3):
        raise ValueError("b must be 1 or 3")
    xs = band_index_range(b, fmin, fmax)
    fm = 1000.0 * G10 ** (xs / b)
    return fm, fm * G10 ** (-1 / (2 * b)), fm * G10 ** (1 / (2 * b))


def nominal_label(fm: float) -> str:
    """Nearest preferred nominal frequency label (display only)."""
    noms = np.array(NOMINAL_THIRD, float)
    n = noms[np.argmin(np.abs(np.log(noms / fm)))]
    return f"{n/1000:g}k" if n >= 1000 else f"{n:g}"


def _overlap_weights(f: np.ndarray, lo: float, hi: float) -> np.ndarray:
    """Fraction of each PSD bin [f-df/2, f+df/2] lying inside [lo, hi]."""
    df = np.gradient(f) if len(f) > 1 else np.array([1.0])
    a = f - df / 2
    bnd = f + df / 2
    ov = np.clip(np.minimum(bnd, hi) - np.maximum(a, lo), 0, None)
    return ov  # in Hz


def band_power_from_psd(f, psd, b: int = 3, fmin: float = 20.0, fmax: float = 20000.0):
    """Integrate a one-sided PSD over ideal band edges -> band mean-square (units^2)."""
    f = np.asarray(f, float)
    psd = np.asarray(psd, float)
    fm, lo, hi = band_centres(b, fmin, fmax)
    fmax_data = f[-1]
    keep = hi <= fmax_data * 1.0001
    fm, lo, hi = fm[keep], lo[keep], hi[keep]
    pw = np.array([np.sum(psd * _overlap_weights(f, l, h)) for l, h in zip(lo, hi)])
    return fm, pw


def band_levels_from_psd(f, psd, ref: float, b: int = 3, fmin: float = 20.0, fmax: float = 20000.0):
    fm, pw = band_power_from_psd(f, psd, b, fmin, fmax)
    with np.errstate(divide="ignore"):
        return fm, 10 * np.log10(np.maximum(pw, 1e-300) / ref ** 2)


def total_from_bands(fm, levels, weighting: str = "Z") -> float:
    fm = np.asarray(fm, float)
    return energy_sum(np.asarray(levels, float) + weighting_db(fm, weighting))


def total_from_psd(f, psd, ref: float, weighting: str = "Z", fmin: float = 10.0, fmax: float = 20000.0) -> float:
    f = np.asarray(f, float)
    m = (f >= fmin) & (f <= fmax)
    df = np.gradient(f)
    w = 10 ** (weighting_db(f[m], weighting) / 10)
    p = float(np.sum(np.asarray(psd)[m] * w * df[m]))
    return 10 * np.log10(max(p, 1e-300) / ref ** 2)


def thirds_to_octaves(f_third, L_third):
    """Energy-sum the three thirds of each octave (exact mid-band frequencies required)."""
    f_third = np.asarray(f_third, float)
    L_third = np.asarray(L_third, float)
    x3 = np.round(3 * np.log(f_third / 1000) / np.log(G10)).astype(int)
    fo, Lo = [], []
    for xo in sorted(set(int(np.round(x / 3)) for x in x3)):
        members = [i for i, x in enumerate(x3) if x in (3 * xo - 1, 3 * xo, 3 * xo + 1)]
        if len(members) == 3:
            fo.append(1000 * G10 ** xo)
            Lo.append(energy_sum(L_third[members]))
    return np.array(fo), np.array(Lo)


def octaves_to_thirds(f_oct, L_oct):
    """ESTIMATE: subdivide each octave into thirds following the local log-level slope, then
    renormalise so each octave's energy is preserved exactly. Returns (f_third, L_third)."""
    f_oct = np.asarray(f_oct, float)
    L_oct = np.asarray(L_oct, float)
    lf = np.log10(f_oct)
    f3, L3 = [], []
    for i, (fo, lo) in enumerate(zip(f_oct, L_oct)):
        sub = fo * G10 ** (np.array([-1, 0, 1]) / 3)
        # spectrum-level slope estimate from neighbours (dB per decade) on per-Hz basis
        dens = L_oct - 10 * np.log10(f_oct * (G10 ** 0.5 - G10 ** -0.5))
        guess = np.interp(np.log10(sub), lf, dens) + 10 * np.log10(sub * (G10 ** (1 / 6) - G10 ** (-1 / 6)))
        corr = lo - energy_sum(guess)
        f3.extend(sub)
        L3.extend(guess + corr)
    return np.array(f3), np.array(L3)


def psd_from_bands(fm, levels, ref: float, f_grid, b: int):
    """ESTIMATE: smooth PSD consistent with band levels (each band's integral preserved)."""
    fm = np.asarray(fm, float)
    levels = np.asarray(levels, float)
    f_grid = np.asarray(f_grid, float)
    bw = fm * (G10 ** (1 / (2 * b)) - G10 ** (-1 / (2 * b)))
    dens_db = levels + 20 * np.log10(ref) - 10 * np.log10(bw)  # 10log10(units^2/Hz)
    lg = np.log10(np.maximum(f_grid, 1e-9))
    d = np.interp(lg, np.log10(fm), dens_db, left=dens_db[0] - 40, right=dens_db[-1] - 40)
    psd = 10 ** (d / 10)
    # fade outside the band range
    lo_edge, hi_edge = fm[0] * G10 ** (-1 / (2 * b)), fm[-1] * G10 ** (1 / (2 * b))
    psd[(f_grid < lo_edge) | (f_grid > hi_edge)] *= 1e-4
    # renormalise per band; bins straddling an edge belong to two bands, so iterate to convergence
    edges = [(c * G10 ** (-1 / (2 * b)), c * G10 ** (1 / (2 * b))) for c in fm]
    wts_all = [_overlap_weights(f_grid, lo, hi) for lo, hi in edges]
    targets = 10 ** (levels / 10) * ref ** 2
    for _ in range(20):
        worst = 0.0
        for wts, target in zip(wts_all, targets):
            cur = np.sum(psd * wts)
            if cur > 0:
                r = target / cur
                psd[wts > 0] *= r
                worst = max(worst, abs(10 * np.log10(r)))
        if worst < 1e-4:
            break
    return psd


def a_weighted_band_levels(fm, levels):
    return np.asarray(levels, float) + a_weighting_db(fm)
