"""Wind and vegetation: layered gusting wind, granular leaf rustle, grass."""
from __future__ import annotations

import numpy as np
from scipy import signal

from .core import (Module, StatefulSOS, bandpass_sos, control_to_audio, derive_seed, highpass_sos, lowpass_sos,
                   ou_process)

CTRL = 100


def gust_signal(seed, kind, duration_s, strength, gustiness, timescale_s=6.0):
    """Shared gust process (log-intensity OU). Same seed -> same gusts for wind and leaves (coherence)."""
    rng = np.random.default_rng(derive_seed(seed, "gust", kind))
    n = int((duration_s + 90) * CTRL)
    g = ou_process(n, 1 / CTRL, 1 / timescale_s, 0.25 + 0.6 * gustiness, rng)
    slow = ou_process(n, 1 / CTRL, 1 / 40.0, 0.3, rng)
    return np.exp(g + slow) * strength


class Wind(Module):
    kind = "wind"
    label = "Wind"
    is_bed = True

    def setup(self):
        p = self.params
        self.strength = float(p.get("strength", 0.5))
        self.gustiness = float(p.get("gustiness", 0.5))
        self.low_freq = bool(p.get("low_freq", True))
        self.I = gust_signal(self.params.get("gust_seed", self.seed), "wind", self.duration_s, 1.0, self.gustiness)
        self.lo = StatefulSOS(bandpass_sos(self.fs, 30, 250, 2), 2)
        self.mid = StatefulSOS(bandpass_sos(self.fs, 200, 1200, 2), 2)
        self.hi = StatefulSOS(bandpass_sos(self.fs, 1000, 6000, 2), 2)
        rng = np.random.default_rng(derive_seed(self.seed, self.kind, "howl"))
        self.howl_f = rng.uniform(350, 900)
        self.howl = StatefulSOS(signal.tf2sos(*signal.iirpeak(self.howl_f, 18, fs=self.fs)), 2)

    def _block(self, k, rng):
        B = self.B
        I = control_to_audio(self.I, k, B, CTRL)[:, None]
        s = self.strength
        n = rng.standard_normal((B, 2))
        out = self.mid(n) * 0.06 * I * (0.4 + s)
        out += self.hi(rng.standard_normal((B, 2))) * 0.025 * I ** 1.8 * s
        if self.low_freq:
            out += self.lo(rng.standard_normal((B, 2))) * 0.10 * I ** 0.8 * (0.3 + s)
        out += self.howl(rng.standard_normal((B, 2))) * 0.01 * np.clip(I - 1.0, 0, None) ** 2 * s
        return out


class Leaves(Module):
    """Granular rustle: noise gated by a dense, crackly grain envelope whose density follows the gusts."""

    kind = "leaves"
    label = "Rustling leaves"
    is_bed = True

    def setup(self):
        p = self.params
        self.activity = float(p.get("activity", 0.5))
        self.I = gust_signal(p.get("gust_seed", self.seed), "wind", self.duration_s, 1.0,
                             float(p.get("gustiness", 0.5)))
        self.bright = StatefulSOS(bandpass_sos(self.fs, 2000, 9000, 2), 2)
        self.soft = StatefulSOS(bandpass_sos(self.fs, 700, 3500, 1), 2)
        self.L = int(0.03 * self.fs)
        tt = np.arange(self.L) / self.fs
        self.kern_fast = np.exp(-tt / 0.004)
        self.kern_slow = np.exp(-tt / 0.012)
        self.tail_f = np.zeros((self.L - 1, 2))
        self.tail_s = np.zeros((self.L - 1, 2))

    def _env(self, rng, rate_t, kern, tail_name):
        B = self.B
        imp = np.zeros((B, 2))
        n = rng.poisson(float(np.sum(rate_t)) / self.fs)
        if n:
            # thinning: draw candidate positions proportional to rate
            p = rate_t / rate_t.sum()
            pos = rng.choice(B, size=n, p=p)
            ch = rng.integers(0, 2, n)
            np.add.at(imp, (pos, ch), rng.lognormal(0, 0.6, n))
            imp[:, :] += 0.35 * imp[:, ::-1]  # partial inter-channel leakage
        y = signal.oaconvolve(imp, kern[:, None], mode="full", axes=0)
        tail = getattr(self, tail_name)
        y[: tail.shape[0]] += tail
        setattr(self, tail_name, y[B:].copy())
        return y[:B]

    def _block(self, k, rng):
        B = self.B
        I = control_to_audio(self.I, k, B, CTRL)
        rate = (40 + 900 * self.activity) * np.clip(I, 0.05, None) ** 2
        e1 = self._env(rng, rate, self.kern_fast, "tail_f")
        e2 = self._env(rng, rate * 0.6, self.kern_slow, "tail_s")
        out = self.bright(rng.standard_normal((B, 2))) * e1 * 0.03
        out += self.soft(rng.standard_normal((B, 2))) * e2 * 0.02
        return out


class Grass(Leaves):
    kind = "grass"
    label = "Grass movement"

    def setup(self):
        super().setup()
        self.bright = StatefulSOS(bandpass_sos(self.fs, 1500, 6000, 1), 2)
        tt = np.arange(self.L) / self.fs
        self.kern_fast = np.exp(-tt / 0.008)

    def _block(self, k, rng):
        return super()._block(k, rng) * 0.6
