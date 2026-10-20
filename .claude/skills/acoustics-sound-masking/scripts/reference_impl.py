#!/usr/bin/env python3
"""Reference implementations of the skill's core equations (numpy + scipy only).

Every numerical example quoted in the skill's markdown is produced by this file.
Run `python reference_impl.py --selftest` to re-verify them.

Units: pressure in Pa, frequency in Hz, levels in dB re 20 uPa unless stated.
"""
import json
import math
import sys

import numpy as np
from scipy import signal

P0 = 20e-6  # Pa, reference sound pressure in air

# --------------------------------------------------------------------------- levels

def spl_from_pressure(p):
    """L_p = 20 log10(p_rms / p0)."""
    prms = float(np.sqrt(np.mean(np.asarray(p, float) ** 2)))
    return 20.0 * math.log10(max(prms, 1e-30) / P0)


def energy_sum(levels_db):
    """Incoherent sum of independent sources: L = 10 log10 sum 10^(Li/10)."""
    l = np.asarray(levels_db, float)
    return 10.0 * np.log10(np.sum(10.0 ** (l / 10.0)))


# --------------------------------------------------------------------------- weightings (IEC 61672-1 analytic forms)

_F1, _F2, _F3, _F4 = 20.598997, 107.65265, 737.86223, 12194.217
A1000 = -2.000  # dB normalisation constants so that A(1 kHz) = C(1 kHz) = 0
C1000 = -0.062


def a_weighting_db(f):
    f = np.asarray(f, float)
    f2 = f ** 2
    ra = (_F4 ** 2 * f2 ** 2) / ((f2 + _F1 ** 2) * np.sqrt((f2 + _F2 ** 2) * (f2 + _F3 ** 2)) * (f2 + _F4 ** 2))
    with np.errstate(divide="ignore"):
        return 20.0 * np.log10(ra) - A1000


def c_weighting_db(f):
    f = np.asarray(f, float)
    f2 = f ** 2
    rc = (_F4 ** 2 * f2) / ((f2 + _F1 ** 2) * (f2 + _F4 ** 2))
    with np.errstate(divide="ignore"):
        return 20.0 * np.log10(rc) - C1000


# --------------------------------------------------------------------------- fractional-octave bands (IEC 61260-1 base-10)

G10 = 10 ** 0.3


def band_centres(b=3, fmin=20.0, fmax=20000.0):
    """Exact mid-band frequencies f_m = 1000 * G^(x/b) (b odd), and nominal labels."""
    xs = np.arange(-60, 61)
    fm = 1000.0 * G10 ** (xs / b)
    keep = (fm >= fmin / G10 ** (1 / (2 * b))) & (fm <= fmax * G10 ** (1 / (2 * b)))
    fm = fm[keep]
    return fm, fm * G10 ** (-1 / (2 * b)), fm * G10 ** (1 / (2 * b))


def band_levels_from_psd(f, psd_pa2_hz, b=3, fmin=20.0, fmax=20000.0):
    """Integrate a one-sided PSD (Pa^2/Hz) over ideal band edges -> band SPL (dB)."""
    fm, lo, hi = band_centres(b, fmin, fmax)
    df = np.gradient(f)
    out = []
    for l, h in zip(lo, hi):
        m = (f >= l) & (f < h)
        e = float(np.sum(psd_pa2_hz[m] * df[m]))
        out.append(10 * math.log10(e / P0 ** 2) if e > 0 else -np.inf)
    return fm, np.array(out)


def welch_psd(x, fs, seg_s=0.5):
    nper = int(2 ** round(math.log2(seg_s * fs)))
    f, p = signal.welch(x, fs, window="hann", nperseg=nper, noverlap=nper // 2, scaling="density", detrend=False)
    return f, p


# --------------------------------------------------------------------------- auditory scales

def erb_hz(f):
    """Glasberg & Moore (1990): ERB_N = 24.7 (4.37 f/1000 + 1)."""
    return 24.7 * (4.37 * np.asarray(f, float) / 1000.0 + 1.0)


def erb_number(f):
    return 21.4 * np.log10(4.37 * np.asarray(f, float) / 1000.0 + 1.0)


def erb_number_to_hz(e):
    return (10 ** (np.asarray(e, float) / 21.4) - 1.0) * 1000.0 / 4.37


def bark_zwicker(f):
    """Zwicker & Terhardt (1980)."""
    f = np.asarray(f, float)
    return 13.0 * np.arctan(0.00076 * f) + 3.5 * np.arctan((f / 7500.0) ** 2)


def bark_traunmuller(f):
    """Traunmuller (1990)."""
    f = np.asarray(f, float)
    return 26.81 * f / (1960.0 + f) - 0.53


def threshold_in_quiet_db(f):
    """Terhardt (1979) approximation of the absolute threshold (dB SPL), as used in many codecs.
    An approximation; ISO 389-7 gives the normative free-field values."""
    k = np.asarray(f, float) / 1000.0
    return 3.64 * k ** -0.8 - 6.5 * np.exp(-0.6 * (k - 3.3) ** 2) + 1e-3 * k ** 4


def roex_weight(f, fc):
    """Symmetric roex(p) auditory filter, p = 4 fc / ERB(fc) (Patterson 1982; Glasberg & Moore 1990).
    W(g) = (1 + p g) exp(-p g), g = |f - fc| / fc. Its equivalent rectangular bandwidth equals ERB(fc)."""
    p = 4.0 * fc / erb_hz(fc)
    g = np.abs(np.asarray(f, float) - fc) / fc
    return (1.0 + p * g) * np.exp(-p * g)


def excitation_pa2(f, psd, centres):
    """Power at the output of each roex filter (Pa^2) for a PSD in Pa^2/Hz."""
    df = np.gradient(f)
    return np.array([np.sum(psd * roex_weight(f, fc) * df) for fc in centres])


def masked_threshold_db(masker_exc_pa2, centres, k_db=-4.0):
    """Power-spectrum model of masking: a target becomes detectable in a filter when its filter-output
    power exceeds K x masker power (K approx -4 dB for tones in broadband noise; frequency dependent).
    Combined with threshold in quiet by power addition."""
    lm = 10 * np.log10(np.maximum(masker_exc_pa2, 1e-30) / P0 ** 2)
    tq = threshold_in_quiet_db(centres)
    return 10 * np.log10(10 ** ((lm + k_db) / 10) + 10 ** (tq / 10))


# --------------------------------------------------------------------------- tonality screening (ECMA-418-1 / ANSI S1.13 style)

def critical_band_hz(f):
    """Zwicker-type critical bandwidth approximation used for TNR/PR screening."""
    f = np.asarray(f, float)
    return 25.0 + 75.0 * (1.0 + 1.4 * (f / 1000.0) ** 2) ** 0.69


def tnr_criterion_db(f):
    """Prominent-tone criterion for tone-to-noise ratio: 8 dB at >=1 kHz, 8 + 8.33 log10(1000/f) below."""
    f = np.asarray(f, float)
    return np.where(f >= 1000, 8.0, 8.0 + 8.33 * np.log10(1000.0 / f))


def pr_criterion_db(f):
    """Prominence-ratio criterion: 9 dB at >=1 kHz, 9 + 10 log10(1000/f) below."""
    f = np.asarray(f, float)
    return np.where(f >= 1000, 9.0, 9.0 + 10.0 * np.log10(1000.0 / f))


# --------------------------------------------------------------------------- ISO 9613-1 atmospheric absorption (published formula)

def atmospheric_absorption_db_per_m(f, t_c=20.0, rh=50.0, pa_kpa=101.325):
    T0, T01, pr = 293.15, 273.16, 101.325
    T = t_c + 273.15
    psat_pr = 10 ** (-6.8346 * (T01 / T) ** 1.261 + 4.6151)
    h = rh * psat_pr * (pr / pa_kpa)
    pa_pr = pa_kpa / pr
    frO = pa_pr * (24.0 + 4.04e4 * h * (0.02 + h) / (0.391 + h))
    frN = pa_pr * (T / T0) ** -0.5 * (9.0 + 280.0 * h * np.exp(-4.170 * ((T / T0) ** (-1 / 3) - 1)))
    f = np.asarray(f, float)
    return 8.686 * f ** 2 * (1.84e-11 / pa_pr * (T / T0) ** 0.5 + (T / T0) ** -2.5 * (
        0.01275 * np.exp(-2239.1 / T) / (frO + f ** 2 / frO) + 0.1068 * np.exp(-3352.0 / T) / (frN + f ** 2 / frN)))


# --------------------------------------------------------------------------- self-test

def _selftest():
    res = []

    def chk(name, value, expected, tol):
        ok = abs(value - expected) <= tol
        res.append({"test": name, "value": round(float(value), 4), "expected": expected, "tol": tol,
                    "status": "PASS" if ok else "FAIL"})

    fs = 48000
    t = np.arange(fs) / fs
    # 1 Pa amplitude sine -> p_rms = 0.7071 Pa -> 90.97 dB
    chk("SPL of 1 Pa-peak sine", spl_from_pressure(np.sin(2 * np.pi * 1000 * t)), 90.969, 0.01)
    chk("SPL of 1 Pa rms", 20 * math.log10(1 / P0), 93.979, 0.001)
    chk("two equal 80 dB sources", energy_sum([80, 80]), 83.010, 0.001)
    chk("80 + 70 dB", energy_sum([80, 70]), 80.414, 0.001)
    chk("ten equal 60 dB sources", energy_sum([60] * 10), 70.0, 1e-9)
    # A/C weighting against IEC 61672-1 Table 3 nominal values
    # IEC 61672-1 tabulates weightings at the EXACT base-10 frequencies 1000*10^(n/10), not at nominal labels
    for n, a in [(-15, -39.4), (-12, -26.2), (-9, -16.1), (-6, -8.6), (-3, -3.2), (0, 0.0),
                 (3, 1.2), (6, 1.0), (9, -1.1), (12, -6.6)]:
        f = 1000 * 10 ** (n / 10)
        chk(f"A({f:.1f} Hz)", float(a_weighting_db(f)), a, 0.1)
    for n, c in [(-15, -3.0), (-12, -0.8), (0, 0.0), (9, -3.0)]:
        f = 1000 * 10 ** (n / 10)
        chk(f"C({f:.1f} Hz)", float(c_weighting_db(f)), c, 0.1)
    fm, lo, hi = band_centres(1, 31.5, 16000)
    chk("octave count 31.5..16k (10 bands)", len(fm), 10, 0)
    chk("octave exact mid 125 Hz", fm[2], 125.89, 0.01)
    fm3, _, _ = band_centres(3, 20, 20000)
    chk("third-octave count 20..20k (31 bands)", len(fm3), 31, 0)
    # Parseval / PSD normalisation: white noise of known rms
    rng = np.random.default_rng(1)
    x = rng.normal(0, 0.1, fs * 10)
    f, p = welch_psd(x, fs)
    chk("Welch PSD integral = variance", float(np.sum(p) * (f[1] - f[0])), 0.01, 0.0003)
    # Band levels of a 1 kHz tone, 94 dB
    tone = math.sqrt(2) * 1.0 * np.sin(2 * np.pi * 1000 * np.arange(fs * 4) / fs)
    f, p = welch_psd(tone, fs)
    fmb, lb = band_levels_from_psd(f, p, 3, 20, 20000)
    i1k = int(np.argmin(abs(fmb - 1000)))
    chk("1 kHz tone 93.98 dB in 1/3-oct band", lb[i1k], 93.979, 0.05)
    # auditory scales
    chk("ERB(1 kHz)", float(erb_hz(1000)), 132.639, 0.001)
    chk("ERB-number(1 kHz)", float(erb_number(1000)), 15.621, 0.001)
    chk("ERB-number round-trip", float(erb_number_to_hz(erb_number(3150))), 3150, 1e-6)
    chk("Bark Zwicker(1 kHz)", float(bark_zwicker(1000)), 8.51, 0.01)
    chk("Bark Traunmuller(1 kHz)", float(bark_traunmuller(1000)), 8.527, 0.01)
    ff = np.linspace(1, 20000, 400000)
    chk("roex ERB equals ERB(1k)", float(np.trapezoid(roex_weight(ff, 1000), ff)), 132.639, 0.5)
    chk("threshold in quiet @1 kHz", float(threshold_in_quiet_db(1000)), 3.37, 0.02)
    chk("critical band @1 kHz (Hz)", float(critical_band_hz(1000)), 162.2, 0.2)
    chk("TNR criterion @250 Hz", float(tnr_criterion_db(250)), 13.015, 0.01)
    chk("PR criterion @250 Hz", float(pr_criterion_db(250)), 15.021, 0.01)
    # Masked threshold of white noise
    fpsd = np.linspace(1, 24000, 48000)
    n0 = (P0 ** 2) * 10 ** (30 / 10)  # spectrum level 30 dB/Hz
    exc = excitation_pa2(fpsd, np.full_like(fpsd, n0), np.array([1000.0]))
    chk("white-noise filter level @1k = 30+10log10(ERB)", 10 * math.log10(exc[0] / P0 ** 2), 30 + 10 * math.log10(132.639), 0.1)
    chk("masked threshold, K=-4 dB", float(masked_threshold_db(exc, np.array([1000.0]))[0]), 30 + 10 * math.log10(132.639) - 4, 0.1)
    # ISO 9613-2 Table 2 octave-band coefficients, 20 C / 70 % RH (dB/km), evaluated at exact mid-band f
    for n, a in [(-6, 1.1), (-3, 2.8), (0, 5.0), (3, 9.0), (6, 22.9), (9, 76.6)]:
        f = 1000 * 10 ** (n / 10)
        v = float(atmospheric_absorption_db_per_m(f, 20.0, 70.0)) * 1000
        chk(f"alpha {f:.0f} Hz, 20C 70% (dB/km)", v, a, max(0.15, 0.03 * a))
    failed = [r for r in res if r["status"] != "PASS"]
    print(json.dumps({"results": res, "passed": len(res) - len(failed), "failed": len(failed)}, indent=1))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_selftest() if "--selftest" in sys.argv else 0)
