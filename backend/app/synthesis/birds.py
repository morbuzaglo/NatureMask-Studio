"""Procedural birds: tonal FM syllables with harmonics, organised into songs by a per-species Markov grammar.

Species profiles are *generic species-like patterns*, not claims about real species.
"""
from __future__ import annotations

import math

import numpy as np
from scipy import signal

from .core import Module, derive_seed, raised_cosine

SPECIES = {
    # name: f range (Hz), syllable dur (s), syllables/song, song interval mean (s), shapes, harmonics(dB), trill
    "warbler": dict(f=(3500, 7500), dur=(0.03, 0.09), n=(6, 16), interval=6.0, shapes=["down", "up", "trill", "arch"],
                    harm=[-14, -26], trill=(18, 35), level=1.0),
    "thrush": dict(f=(1600, 4200), dur=(0.08, 0.25), n=(3, 7), interval=8.0, shapes=["arch", "flat", "down", "up"],
                   harm=[-10, -20], trill=(6, 12), level=1.0),
    "finch": dict(f=(3000, 6500), dur=(0.02, 0.06), n=(4, 10), interval=5.0, shapes=["down", "chirp", "up"],
                  harm=[-16, -28], trill=(20, 30), level=0.8),
    "dove": dict(f=(380, 650), dur=(0.18, 0.45), n=(3, 5), interval=14.0, shapes=["coo"], harm=[-8, -18],
                 trill=(0, 0), level=0.7),
    "distant": dict(f=(2200, 6000), dur=(0.04, 0.12), n=(2, 6), interval=7.0, shapes=["down", "up", "arch"],
                    harm=[-20, -35], trill=(10, 25), level=0.35),
}


def syllable(rng, fs, sp, shape=None):
    dur = rng.uniform(*sp["dur"])
    n = max(8, int(dur * fs))
    x = np.linspace(0, 1, n)
    f0, f1 = sp["f"]
    fc = rng.uniform(f0, f1)
    span = rng.uniform(0.1, 0.45) * fc
    shape = shape or rng.choice(sp["shapes"])
    if shape == "down":
        fr = fc + span * (0.5 - x)
    elif shape == "up":
        fr = fc + span * (x - 0.5)
    elif shape == "arch":
        fr = fc + span * (0.5 - 2 * (x - 0.5) ** 2) - span * 0.25
    elif shape == "chirp":
        fr = fc + span * np.exp(-6 * x) - span * 0.3
    elif shape == "coo":
        fr = fc * (1 + 0.06 * np.sin(np.pi * x) - 0.04 * x)
    elif shape == "trill":
        rate = rng.uniform(*sp["trill"]) if sp["trill"][1] > 0 else 0
        fr = fc + 0.35 * span * np.sin(2 * np.pi * rate * x * dur)
    else:
        fr = np.full(n, fc)
    fr = np.clip(fr, 150, 0.42 * fs)
    phase = 2 * np.pi * np.cumsum(fr) / fs + rng.uniform(0, 2 * np.pi)
    wave = np.sin(phase)
    for i, hdb in enumerate(sp["harm"]):
        h = i + 2
        mask = fr * h < 0.45 * fs
        wave += 10 ** (hdb / 20) * np.sin(h * phase) * mask
    env = np.sin(np.pi * x) ** rng.uniform(0.6, 1.6)
    am = 1 + 0.15 * np.sin(2 * np.pi * rng.uniform(30, 90) * x * dur)
    return wave * env * am, shape


def song(rng, fs, sp):
    """A song: sequence of syllables from a small first-order Markov grammar over syllable types."""
    types = list(sp["shapes"])
    k = len(types)
    trans = rng.dirichlet(np.ones(k) * 0.6, size=k)
    n_syl = int(rng.integers(sp["n"][0], sp["n"][1] + 1))
    state = int(rng.integers(0, k))
    parts = []
    gap_mean = 0.035 if sp["dur"][1] < 0.1 else 0.09
    reps = 0
    prev = None
    for _ in range(n_syl):
        if prev is not None and reps < 3 and rng.random() < 0.45:
            syl = prev  # repetitions are typical of song
            reps += 1
        else:
            syl, _ = syllable(rng, fs, sp, types[state])
            reps = 0
            state = int(rng.choice(k, p=trans[state]))
        prev = syl
        parts.append(syl * rng.uniform(0.75, 1.0))
        parts.append(np.zeros(int(rng.gamma(4, gap_mean / 4) * fs)))
    return np.concatenate(parts)


class Birds(Module):
    kind = "birds"
    label = "Birdsong"
    tonal_fraction = 0.8

    def setup(self):
        p = self.params
        self.activity = float(p.get("activity", 0.5))          # density multiplier 0..1
        self.pitch = float(p.get("pitch", 1.0))                # pitch scale
        self.species = p.get("species", ["warbler", "thrush", "finch"])
        self.distance = float(p.get("distance", 0.3))          # 0 near .. 1 far
        rng = np.random.default_rng(derive_seed(self.seed, self.kind, "birds"))
        # each individual bird: species, position, its own rate
        nb = int(p.get("individuals", 3 + round(4 * self.activity)))
        self.birds = []
        for i in range(nb):
            sp = self.species[i % len(self.species)]
            self.birds.append({"sp": sp, "pan": float(rng.uniform(-0.9, 0.9)),
                               "dist": float(np.clip(self.distance + rng.normal(0, 0.2), 0, 1)),
                               "rate": 1.0 / SPECIES[sp]["interval"] * (0.4 + 1.2 * self.activity) * rng.uniform(0.6, 1.4)})
        self.lp_cache = {}

    def _distance_filter(self, x, dist):
        # air absorption-like low-pass + level drop for distance (heuristic mapping of 0..1 to ~5..80 m)
        fc = 12000 - 8000 * dist
        key = int(fc / 250)
        if key not in self.lp_cache:
            self.lp_cache[key] = signal.butter(2, min(key * 250, 0.45 * self.fs), fs=self.fs, output="sos")
        return signal.sosfilt(self.lp_cache[key], x) * 10 ** (-18 * dist / 20)

    def _block(self, k, rng):
        out = np.zeros((self.B, 2))
        sp_scale = self.pitch
        for b in self.birds:
            n = rng.poisson(b["rate"])
            for _ in range(n):
                sp = dict(SPECIES[b["sp"]])
                sp["f"] = (sp["f"][0] * sp_scale, sp["f"][1] * sp_scale)
                w = song(rng, self.fs, sp) * 0.06 * sp["level"]
                w = self._distance_filter(w, b["dist"])
                w = np.concatenate([w, np.zeros(int(0.05 * self.fs))])
                # very short early reflection / diffuse tail for outdoor plausibility
                d = int(rng.uniform(0.015, 0.04) * self.fs)
                w[d:] += 0.18 * w[:-d]
                th = (b["pan"] + 1) * math.pi / 4
                st = np.stack([w * math.cos(th), w * math.sin(th)], axis=1)
                self.add_event(out, int(rng.integers(0, self.B)), st)
        return out


class Woodpecker(Module):
    kind = "woodpecker"
    label = "Distant woodpecker"
    tonal_fraction = 0.3

    def setup(self):
        self.rate = float(self.params.get("rate", 0.03))  # drums per second

    def _block(self, k, rng):
        out = np.zeros((self.B, 2))
        for _ in range(rng.poisson(self.rate)):
            hits = int(rng.integers(12, 25))
            hz = rng.uniform(14, 20)
            L = int((hits / hz + 0.1) * self.fs)
            w = np.zeros(L)
            f_res = rng.uniform(700, 1300)
            tk = np.arange(int(0.03 * self.fs)) / self.fs
            click = np.sin(2 * np.pi * f_res * tk) * np.exp(-tk / 0.004)
            for h in range(hits):
                i = int(h / hz * self.fs)
                amp = math.exp(-h / hits * 1.2)
                seg = w[i:i + len(click)]
                seg += amp * click[:len(seg)]
            w *= 0.05
            th = (rng.uniform(-0.8, 0.8) + 1) * math.pi / 4
            self.add_event(out, int(rng.integers(0, self.B)), np.stack([w * math.cos(th), w * math.sin(th)], 1))
        return out


class Owl(Module):
    kind = "owl"
    label = "Owl (night)"
    tonal_fraction = 0.9

    def setup(self):
        self.rate = float(self.params.get("rate", 0.04))

    def _block(self, k, rng):
        out = np.zeros((self.B, 2))
        for _ in range(rng.poisson(self.rate)):
            f = rng.uniform(380, 480)
            parts = []
            for d, df in [(0.35, 0.0), (0.12, -0.03), (0.6, -0.05)]:
                n = int(d * self.fs)
                x = np.linspace(0, 1, n)
                fr = f * (1 + df + 0.03 * np.sin(np.pi * x))
                ph = 2 * np.pi * np.cumsum(fr) / self.fs
                parts.append((np.sin(ph) + 0.15 * np.sin(2 * ph)) * np.sin(np.pi * x) ** 0.7)
                parts.append(np.zeros(int(0.25 * self.fs)))
            w = np.concatenate(parts) * 0.04
            th = (rng.uniform(-0.7, 0.7) + 1) * math.pi / 4
            self.add_event(out, int(rng.integers(0, self.B)), np.stack([w * math.cos(th), w * math.sin(th)], 1))
        return out
