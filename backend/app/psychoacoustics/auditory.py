"""Auditory scales and filters (ERB, Bark, roex), threshold in quiet. See skill references/psychoacoustics.md."""
from __future__ import annotations

import numpy as np


def erb_hz(f):
    return 24.7 * (4.37 * np.asarray(f, float) / 1000.0 + 1.0)


def erb_number(f):
    return 21.4 * np.log10(4.37 * np.asarray(f, float) / 1000.0 + 1.0)


def erb_number_to_hz(e):
    return (10 ** (np.asarray(e, float) / 21.4) - 1.0) * 1000.0 / 4.37


def bark(f):
    f = np.asarray(f, float)
    return 13.0 * np.arctan(0.00076 * f) + 3.5 * np.arctan((f / 7500.0) ** 2)


def erb_band_centres(fmin: float = 50.0, fmax: float = 16000.0, step: float = 1.0):
    e = np.arange(erb_number(fmin), erb_number(fmax) + 1e-9, step)
    return erb_number_to_hz(e)


def threshold_in_quiet_db(f):
    """Terhardt (1979) approximation (dB SPL). ISO 389-7 gives normative values; this is an approximation."""
    k = np.maximum(np.asarray(f, float), 20.0) / 1000.0
    return 3.64 * k ** -0.8 - 6.5 * np.exp(-0.6 * (k - 3.3) ** 2) + 1e-3 * k ** 4


def roex_matrix(f, centres):
    """W[b, k] = roex(p) weight of PSD bin k for filter b, times bin width (so W @ psd = filter power)."""
    f = np.asarray(f, float)
    c = np.asarray(centres, float)[:, None]
    p = 4.0 * c / erb_hz(c)
    g = np.abs(f[None, :] - c) / c
    w = (1.0 + p * g) * np.exp(-p * g)
    w[g > 4.0] = 0.0
    df = np.gradient(f)[None, :]
    return w * df


def filter_powers(f, psd, centres):
    return roex_matrix(f, centres) @ np.asarray(psd, float)
