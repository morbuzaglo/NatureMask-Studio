"""Synthetic target reconstruction from a spectrum (SPECTRUM_ONLY inputs) — always labelled
'SYNTHETIC APPROXIMATION'. Also a library of clearly synthetic demo machines."""
from __future__ import annotations

import math

import numpy as np
from scipy import signal

from .core import Module, StatefulFIR, derive_seed

SYNTH_LABEL = "SYNTHETIC APPROXIMATION — reconstructed from spectrum data, not the actual machine recording"


def shaping_fir(f_grid, psd, fs, numtaps=8191):
    """FIR whose output for unit-variance white noise has one-sided PSD = psd (units^2/Hz)."""
    mag = np.sqrt(np.maximum(psd, 0) * fs / 2.0)
    f = np.asarray(f_grid, float)
    if f[0] > 0:
        f = np.concatenate([[0.0], f])
        mag = np.concatenate([[0.0], mag])
    if f[-1] < fs / 2:
        f = np.concatenate([f, [fs / 2]])
        mag = np.concatenate([mag, [mag[-1]]])
    keep = np.concatenate([[True], np.diff(f) > 0])
    f, mag = f[keep], mag[keep]
    # resample on a log grid (firwin2 needs a moderate number of points)
    fg = np.concatenate([[0], np.geomspace(10, fs / 2 * 0.999, 1500), [fs / 2]])
    mg = np.interp(fg, f, mag)
    mg[0] = 0.0
    return signal.firwin2(numtaps, fg, mg, fs=fs, window="blackmanharris")


class SpectrumTarget(Module):
    """Broadband shaped noise + tonal components + temporal pattern (stationary/intermittent/varying)."""

    kind = "target"
    label = "Synthetic target"

    def setup(self):
        p = self.params
        self.fir = StatefulFIR(shaping_fir(np.asarray(p["f"]), np.asarray(p["psd"]), self.fs), 2)
        self.tones = [dict(t) for t in p.get("tones", [])]  # {"f": Hz, "rms": units}
        for i, t in enumerate(self.tones):
            t["ph"] = 0.37 * i
        self.pattern = p.get("pattern", "stationary")
        self.on_s, self.off_s = float(p.get("on_s", 3.0)), float(p.get("off_s", 2.0))
        self.stereo_corr = 0.9  # machine is a single source: highly correlated channels

    def _gate(self, k):
        t = (k * self.B + np.arange(self.B)) / self.fs
        if self.pattern == "intermittent":
            per = self.on_s + self.off_s
            ph = t % per
            ramp = 0.05
            g = np.clip(np.minimum(ph / ramp, (self.on_s - ph) / ramp), 0, 1)
            return g
        if self.pattern == "varying":
            return 10 ** ((4 * np.sin(2 * np.pi * t / 7.0) + 2 * np.sin(2 * np.pi * t / 2.3)) / 20)
        return np.ones_like(t)

    def _block(self, k, rng):
        B = self.B
        n = rng.standard_normal(B)
        x = self.fir(np.stack([n, n], axis=1))[:, 0]
        t = np.arange(B) / self.fs
        for tn in self.tones:
            ph = tn["ph"] + 2 * np.pi * tn["f"] * t
            x = x + math.sqrt(2) * tn["rms"] * np.sin(ph)
            tn["ph"] = float((ph[-1] + 2 * np.pi * tn["f"] / self.fs) % (2 * np.pi))
        x = x * self._gate(k)
        return np.stack([x, x], axis=1)


def demo_machine_spectrum(kind: str):
    """Clearly synthetic demo targets (third-octave Lp in dB re 20 uPa at the listener + tones).
    Plausible engineering shapes; NOT measurements of real products."""
    from ..acoustics.bands import band_centres
    fm, _, _ = band_centres(3, 25, 16000)
    lf = np.log2(fm / 1000.0)
    if kind == "drill":
        L = 66 - 4.0 * (lf - 1.2) ** 2 + 2.0 * np.exp(-((lf + 3) ** 2))
        tones = [{"f": 2400.0, "level_db": 68.0}, {"f": 4800.0, "level_db": 58.0}, {"f": 120.0, "level_db": 55.0}]
        pattern = "intermittent"
    elif kind == "grinder_hf":
        L = 62 - 3.0 * (lf - 2.6) ** 2
        tones = [{"f": 6300.0, "level_db": 66.0}]
        pattern = "stationary"
    elif kind == "generator_lf":
        L = 70 - 3.5 * (lf + 2.3) ** 2 - 2 * np.clip(lf, 0, None) ** 2
        tones = [{"f": 50.0, "level_db": 72.0}, {"f": 100.0, "level_db": 74.0}, {"f": 150.0, "level_db": 66.0}]
        pattern = "stationary"
    elif kind == "fan":
        L = 64 - 2.5 * (lf + 1.5) ** 2
        tones = [{"f": 240.0, "level_db": 63.0}]
        pattern = "stationary"
    else:
        raise ValueError(kind)
    return fm, L, tones, pattern
