"""Insects (crickets, cicadas, night insects) and frogs."""
from __future__ import annotations

import math

import numpy as np

from .core import Module, StatefulSOS, bandpass_sos, control_to_audio, derive_seed, ou_process

CTRL = 100


def dolbear_chirps_per_min(temp_c: float) -> float:
    """Dolbear's law (1897, snowy tree cricket): T(F) = 50 + (N - 40)/4  =>  N = 4 (T_F - 50) + 40."""
    tf = temp_c * 9 / 5 + 32
    return max(10.0, 4 * (tf - 50) + 40)


class Crickets(Module):
    kind = "crickets"
    label = "Crickets"
    tonal_fraction = 0.9

    def setup(self):
        p = self.params
        self.temp_c = float(p.get("temperature_c", 22.0))
        self.n = int(p.get("individuals", 6))
        self.density = float(p.get("density", 0.6))
        rng = np.random.default_rng(derive_seed(self.seed, self.kind, "voices"))
        base = dolbear_chirps_per_min(self.temp_c) / 60.0
        self.voices = []
        for i in range(self.n):
            self.voices.append({
                "f": float(rng.uniform(3800, 5200)), "rate": base * rng.uniform(0.85, 1.15),
                "pulses": int(rng.integers(2, 5)), "pulse_hz": float(rng.uniform(25, 40)),
                "phase_t": float(rng.uniform(0, 1)), "pan": float(rng.uniform(-0.9, 0.9)),
                "amp": float(rng.uniform(0.3, 1.0)) * 10 ** (-rng.uniform(0, 14) / 20),
                "ph": float(rng.uniform(0, 2 * np.pi)), "active": float(rng.uniform(0.5, 1.0)),
            })

    def _block(self, k, rng):
        B, fs = self.B, self.fs
        t = (k * B + np.arange(B)) / fs
        out = np.zeros((B, 2))
        for vi, v in enumerate(self.voices):
            period = 1.0 / v["rate"]
            tt = t + v["phase_t"] * period
            local = tt % period
            chirp_no = np.floor(tt / period)
            # per-chirp on/off decided by a deterministic hash of (voice, chirp index): natural pauses
            # without cutting a chirp at block boundaries
            u = np.modf(np.abs(np.sin(chirp_no * 12.9898 + (vi + 1) * 78.233 + self.seed % 1000)) * 43758.5453)[0]
            p_on = max(0.15, v["active"] * (0.5 + 0.5 * self.density))
            idx = np.floor(local * v["pulse_hz"])
            within = local * v["pulse_hz"] - idx
            env = np.where((idx < v["pulses"]) & (within < 0.6) & (u < p_on), np.sin(np.pi * within / 0.6) ** 2, 0.0)
            ph = v["ph"] + 2 * np.pi * v["f"] * np.arange(B) / fs
            v["ph"] = float((ph[-1] + 2 * np.pi * v["f"] / fs) % (2 * np.pi))
            s = env * np.sin(ph) * v["amp"] * 0.02 * (1 + 0.1 * np.sin(3 * ph))
            th = (v["pan"] + 1) * math.pi / 4
            out[:, 0] += s * math.cos(th)
            out[:, 1] += s * math.sin(th)
        return out


class Cicadas(Module):
    kind = "cicadas"
    label = "Cicadas"
    tonal_fraction = 0.5

    def setup(self):
        p = self.params
        self.intensity = float(p.get("intensity", 0.5))
        rng = np.random.default_rng(derive_seed(self.seed, self.kind, "ctrl"))
        n = int((self.duration_s + 90) * CTRL)
        # chorus swells: smooth on/off with 10-40 s structure
        self.swell = 1 / (1 + np.exp(-3 * ou_process(n, 1 / CTRL, 1 / 15.0, 1.2, rng)))
        self.band = StatefulSOS(bandpass_sos(self.fs, 4200, 8000, 2), 2)
        self.am_hz = float(rng.uniform(120, 260))
        self.am_ph = 0.0

    def _block(self, k, rng):
        B, fs = self.B, self.fs
        sw = control_to_audio(self.swell, k, B, CTRL)
        ph = self.am_ph + 2 * np.pi * self.am_hz * np.arange(B) / fs
        self.am_ph = float((ph[-1] + 2 * np.pi * self.am_hz / fs) % (2 * np.pi))
        am = (0.55 + 0.45 * np.abs(np.sin(ph))) ** 2
        x = self.band(rng.standard_normal((B, 2)))
        return x * (am * sw * (0.03 + 0.06 * self.intensity))[:, None]


class NightInsects(Crickets):
    kind = "night_insects"
    label = "Night insects"

    def setup(self):
        self.params.setdefault("individuals", 14)
        self.params.setdefault("temperature_c", 18.0)
        super().setup()
        for v in self.voices:
            v["f"] *= np.random.default_rng(derive_seed(self.seed, "ni", v["f"])).uniform(0.85, 1.35)
            v["amp"] *= 0.6


class Frogs(Module):
    kind = "frogs"
    label = "Frogs"
    tonal_fraction = 0.6

    def setup(self):
        p = self.params
        self.activity = float(p.get("activity", 0.5))
        rng = np.random.default_rng(derive_seed(self.seed, self.kind, "voices"))
        self.voices = [{"f0": float(rng.uniform(250, 700)), "pulse": float(rng.uniform(8, 30)),
                        "pan": float(rng.uniform(-0.8, 0.8)), "rate": float(rng.uniform(0.2, 0.6)) * (0.3 + self.activity)}
                       for _ in range(int(p.get("individuals", 4)))]

    def _block(self, k, rng):
        out = np.zeros((self.B, 2))
        fs = self.fs
        for v in self.voices:
            for _ in range(rng.poisson(v["rate"])):
                n_croak = int(rng.integers(1, 4))
                parts = []
                for _c in range(n_croak):
                    d = rng.uniform(0.15, 0.4)
                    n = int(d * fs)
                    t = np.arange(n) / fs
                    within = (t * v["pulse"]) % 1.0
                    # smooth per-pulse envelope (no hard gating -> no broadband clicks)
                    pulses = np.where(within < 0.7, np.sin(np.pi * within / 0.7) ** 2, 0.0) * np.exp(-within * 2)
                    ph = 2 * np.pi * v["f0"] * t
                    w = sum(a * np.sin(h * ph) for h, a in [(1, 1.0), (2, 0.6), (3, 0.35), (5, 0.15)])
                    env = np.sin(np.pi * t / d) ** 0.5
                    parts.append(w * pulses * env)
                    parts.append(np.zeros(int(rng.uniform(0.08, 0.25) * fs)))
                w = np.concatenate(parts) * 0.025
                th = (v["pan"] + 1) * math.pi / 4
                self.add_event(out, int(rng.integers(0, self.B)), np.stack([w * math.cos(th), w * math.sin(th)], 1))
        return out


class Ambience(Module):
    """Very low-level natural 'air' bed: soft, slowly drifting pink-ish noise (distant environment)."""

    kind = "ambience"
    label = "Distant ambience"
    is_bed = True
    tonal_fraction = 0.0

    def setup(self):
        rng = np.random.default_rng(derive_seed(self.seed, self.kind, "ctrl"))
        n = int((self.duration_s + 90) * CTRL)
        self.drift = np.exp(0.3 * ou_process(n, 1 / CTRL, 1 / 30.0, 1.0, rng))
        self.f1 = StatefulSOS(bandpass_sos(self.fs, 60, 1500, 1), 2)
        self.f2 = StatefulSOS(bandpass_sos(self.fs, 1000, 5000, 1), 2)

    def _block(self, k, rng):
        d = control_to_audio(self.drift, k, self.B, CTRL)[:, None]
        x = self.f1(rng.standard_normal((self.B, 2))) * 0.02 + self.f2(rng.standard_normal((self.B, 2))) * 0.004
        return x * d
