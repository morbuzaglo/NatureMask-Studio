"""Water sounds: stream, waterfall, rain, drips, waves. Physically inspired (bubble resonance, impacts)."""
from __future__ import annotations

import math

import numpy as np

from .core import (Module, StatefulSOS, bandpass_sos, control_to_audio, derive_seed, highpass_sos, lowpass_sos,
                   ou_process)

CTRL = 100  # control rate (Hz)


def bubble_cloud(rng, n_events, B, fs, rmin_mm, rmax_mm, amp_scale, xi=0.1, width=0.8, max_len_s=0.05):
    """Vectorised Minnaert bubbles: f0 = 3.26/a (a radius in m), exponential decay, rising pitch.

    Returns (offsets[int], waves[(N, L)], pans[(N,)]). Decay time tau = clip(2.6/f0^0.8, 4..30 ms) is an
    engineering fit giving ~10 ms at 1 kHz (heuristic, see skill synthesis-methods.md).
    """
    if n_events <= 0:
        return np.zeros(0, int), np.zeros((0, 1)), np.zeros(0)
    a = np.exp(rng.uniform(math.log(rmin_mm), math.log(rmax_mm), n_events)) / 1000.0
    f0 = 3.26 / a
    f0 = np.minimum(f0, 0.42 * fs)
    tau = np.clip(2.6 / f0 ** 0.8, 0.004, 0.03)
    L = int(max_len_s * fs)
    t = np.arange(L)[None, :] / fs
    ph = 2 * np.pi * f0[:, None] * (t + xi * t * t / (2 * tau[:, None]))
    env = np.exp(-t / tau[:, None]) * np.minimum(1.0, t * fs / 24.0)
    amp = amp_scale * (a / 0.003) ** 0.5 * rng.lognormal(0, 0.5, n_events)
    waves = amp[:, None] * env * np.sin(ph + rng.uniform(0, 2 * np.pi, n_events)[:, None])
    offsets = rng.integers(0, B, n_events)
    pans = rng.uniform(-width, width, n_events)
    return offsets, waves, pans


def add_mono_events(module, out, offsets, waves, pans):
    L = waves.shape[1]
    for o, w, p in zip(offsets, waves, pans):
        th = (p + 1) * math.pi / 4
        st = np.empty((L, 2))
        st[:, 0] = w * math.cos(th)
        st[:, 1] = w * math.sin(th)
        module.add_event(out, int(o), st)


class Stream(Module):
    kind = "stream"
    label = "Gentle stream"
    is_bed = True
    tonal_fraction = 0.15

    def setup(self):
        p = self.params
        self.flow = float(p.get("flow", 0.5))          # 0..1
        rng = np.random.default_rng(derive_seed(self.seed, self.kind, "ctrl"))
        n = int((self.duration_s + 90) * CTRL)
        self.ctrl = 0.5 * ou_process(n, 1 / CTRL, 1 / 8.0, 0.35, rng)  # slow flow variation (log-domain)
        self.lp = StatefulSOS(bandpass_sos(self.fs, 150, 5000, 2), 2)
        self.hiss = StatefulSOS(bandpass_sos(self.fs, 1500, 9000, 2), 2)

    def _block(self, k, rng):
        B = self.B
        g = np.exp(control_to_audio(self.ctrl, k, B, CTRL))
        rate = (300 + 1200 * self.flow) * float(np.mean(g))
        out = np.zeros((B, 2))
        offs, waves, pans = bubble_cloud(rng, rng.poisson(rate), B, self.fs, 0.8, 5.0, 0.010, width=0.9)
        add_mono_events(self, out, offs, waves, pans)
        noise = rng.standard_normal((B, 2))
        turb = self.lp(noise) * (0.05 + 0.06 * self.flow) + self.hiss(rng.standard_normal((B, 2))) * 0.012
        return out + turb * g[:, None]


class Waterfall(Stream):
    kind = "waterfall"
    label = "Small waterfall"
    tonal_fraction = 0.05

    def setup(self):
        super().setup()
        self.flow = float(self.params.get("flow", 0.9))
        self.rumble = StatefulSOS(lowpass_sos(self.fs, 400, 2), 2)

    def _block(self, k, rng):
        base = super()._block(k, rng)
        r = self.rumble(rng.standard_normal((self.B, 2))) * 0.12
        return base * 1.4 + r


class Rain(Module):
    kind = "rain"
    label = "Rain"
    is_bed = True
    tonal_fraction = 0.05

    def setup(self):
        p = self.params
        self.intensity = float(p.get("intensity", 0.5))
        self.surface = p.get("surface", "leaves")  # leaves | ground | water
        rng = np.random.default_rng(derive_seed(self.seed, self.kind, "ctrl"))
        n = int((self.duration_s + 90) * CTRL)
        self.ctrl = 0.4 * ou_process(n, 1 / CTRL, 1 / 20.0, 0.5, rng)
        self.bed = StatefulSOS(bandpass_sos(self.fs, 300, 9000, 1), 2)
        self.body = {"leaves": (1500, 9000), "ground": (200, 3000), "water": (600, 6000)}[self.surface]

    def _block(self, k, rng):
        B, fs = self.B, self.fs
        g = np.exp(control_to_audio(self.ctrl, k, B, CTRL))
        rate = (150 + 2500 * self.intensity ** 1.5) * float(np.mean(g))
        n = rng.poisson(rate)
        out = np.zeros((B, 2))
        if n:
            L = int(0.012 * fs)
            t = np.arange(L)[None, :] / fs
            tau = rng.uniform(0.0008, 0.004, n)[:, None]
            amp = 0.02 * np.minimum(rng.lognormal(0, 0.45, n), 3.0)[:, None]  # bounded drop loudness
            burst = rng.standard_normal((n, L)) * np.exp(-t / tau) * np.minimum(1.0, t * self.fs / 6.0) * amp
            # crude spectral colouring per surface: first-difference (brighter) or running mean (duller)
            lo, hi = self.body
            if hi > 6000:
                burst = np.diff(burst, axis=1, prepend=0)
            elif hi < 4000:
                burst = 0.5 * (burst + np.roll(burst, 1, axis=1))
            add_mono_events(self, out, rng.integers(0, B, n), burst, rng.uniform(-1, 1, n))
            if self.surface == "water":
                offs, waves, pans = bubble_cloud(rng, int(n * 0.15), B, fs, 0.5, 2.0, 0.006)
                add_mono_events(self, out, offs, waves, pans)
        bed = self.bed(rng.standard_normal((B, 2))) * (0.01 + 0.05 * self.intensity) * g[:, None]
        return out + bed


class Drips(Module):
    kind = "drips"
    label = "Dripping water"
    tonal_fraction = 0.6

    def setup(self):
        self.rate = float(self.params.get("rate", 1.5))  # drips per second

    def _block(self, k, rng):
        out = np.zeros((self.B, 2))
        n = rng.poisson(self.rate)
        offs, waves, pans = bubble_cloud(rng, n, self.B, self.fs, 1.5, 4.0, 0.08, xi=0.25, width=0.6, max_len_s=0.12)
        add_mono_events(self, out, offs, waves, pans)
        return out


class Waves(Module):
    kind = "waves"
    label = "Distant waves"
    is_bed = True
    tonal_fraction = 0.0

    def setup(self):
        rng = np.random.default_rng(derive_seed(self.seed, self.kind, "ctrl"))
        n = int((self.duration_s + 90) * CTRL)
        env = np.zeros(n)
        t = 0.0
        size = float(self.params.get("size", 0.5))
        while t < n / CTRL:
            period = rng.uniform(6, 14)
            peak = rng.uniform(0.5, 1.0)
            i0 = int(t * CTRL)
            m = int(period * CTRL)
            x = np.arange(m) / m
            shape = np.where(x < 0.3, (x / 0.3) ** 2, np.exp(-(x - 0.3) / 0.25))  # fast rise, slow wash
            env[i0:i0 + m] = np.maximum(env[i0:i0 + m], peak * shape[: max(0, min(m, n - i0))])
            t += period * rng.uniform(0.75, 1.0)
        self.env = 0.15 + env
        self.size = size
        self.low = StatefulSOS(lowpass_sos(self.fs, 500, 2), 2)
        self.mid = StatefulSOS(bandpass_sos(self.fs, 400, 2500, 1), 2)
        self.fizz = StatefulSOS(bandpass_sos(self.fs, 2500, 10000, 1), 2)

    def _block(self, k, rng):
        B = self.B
        e = control_to_audio(self.env, k, B, CTRL)
        d = np.gradient(e) * self.fs  # envelope slope per second
        wash = np.clip(-d * 0.8, 0, 1)  # fizz while the wave recedes
        lo = self.low(rng.standard_normal((B, 2))) * (0.10 + 0.10 * self.size) * e[:, None]
        mi = self.mid(rng.standard_normal((B, 2))) * 0.05 * e[:, None] ** 1.5
        fz = self.fizz(rng.standard_normal((B, 2))) * 0.03 * (wash[:, None] + 0.1 * e[:, None])
        return lo + mi + fz
