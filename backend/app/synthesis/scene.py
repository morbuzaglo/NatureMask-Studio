"""Scene: a set of modules with levels, optional bed EQ and slow adaptation; chunked rendering."""
from __future__ import annotations

import math
from functools import lru_cache

import numpy as np
from scipy import signal

from ..acoustics.bands import G10
from ..dsp.spectral import welch_psd
from .birds import Birds, Owl, Woodpecker
from .core import StatefulFIR, derive_seed
from .insects import Ambience, Cicadas, Crickets, Frogs, NightInsects
from .water import Drips, Rain, Stream, Waterfall, Waves
from .wind import Grass, Leaves, Wind

MODULE_TYPES = {c.kind: c for c in [Birds, Owl, Woodpecker, Ambience, Cicadas, Crickets, Frogs, NightInsects,
                                    Drips, Rain, Stream, Waterfall, Waves, Grass, Leaves, Wind]}
EQ_BANDS_HZ = [1000 * G10 ** x for x in range(-5, 5)]  # 31.6 Hz ... 15.8 kHz (10 octave control points)
ADAPT_RATE = 10  # Hz, control rate of the adaptation gain curve


def module_catalog():
    return [{"type": k, "label": c.label, "is_bed": c.is_bed, "tonal_fraction": c.tonal_fraction}
            for k, c in sorted(MODULE_TYPES.items())]


def eq_fir(gains_db, fs, numtaps=2047):
    """Linear-phase FIR from 10 octave-spaced gains (dB), log-frequency interpolation."""
    f = np.concatenate([[0], np.geomspace(20, fs / 2 * 0.999, 400), [fs / 2]])
    g = np.interp(np.log10(np.maximum(f, 1)), np.log10(EQ_BANDS_HZ), np.asarray(gains_db, float))
    return signal.firwin2(numtaps, f, 10 ** (g / 20), fs=fs)


class Scene:
    def __init__(self, config: dict, fs: int = 48000, duration_s: float = 60.0, seed: int = 1,
                 master_db: float = 0.0, module_gains_db: dict | None = None, bed_eq: dict | None = None,
                 adaptation_db: np.ndarray | None = None, extra_s: float = 0.0):
        self.config = config
        self.fs = int(fs)
        self.seed = int(seed)
        self.duration_s = float(duration_s)
        self.master_db = float(master_db)
        self.module_gains_db = dict(module_gains_db or {})
        self.adaptation = None if adaptation_db is None else np.asarray(adaptation_db, float)
        self.items = []
        for m in config.get("modules", []):
            if not m.get("enabled", True):
                continue
            cls = MODULE_TYPES[m["type"]]
            params = dict(m.get("params", {}))
            params.setdefault("gust_seed", derive_seed(self.seed, "gusts"))  # shared gusts -> coherent wind/leaves
            mod = cls(self.fs, derive_seed(self.seed, m["id"]), params, self.duration_s + extra_s + 5)
            eq = None
            if bed_eq and m["id"] in bed_eq and cls.is_bed:
                eq = StatefulFIR(eq_fir(bed_eq[m["id"]], self.fs), 2)
            self.items.append({"id": m["id"], "type": m["type"], "mod": mod, "level_db": float(m.get("level_db", 0)),
                               "eq": eq, "is_bed": cls.is_bed, "eq_delay": 1023 if eq is not None else 0})

    def gain_db(self, item) -> float:
        return self.master_db + item["level_db"] + self.module_gains_db.get(item["id"], 0.0)

    def _adapt(self, start, n, depth):
        if self.adaptation is None:
            return 1.0
        t = (start + np.arange(n)) / self.fs
        a = np.interp(t * ADAPT_RATE, np.arange(len(self.adaptation)), self.adaptation)
        return (10 ** (depth * a / 20))[:, None]

    def render(self, start: int, n: int, only: str | None = None) -> np.ndarray:
        out = np.zeros((n, 2))
        for it in self.items:
            if only and it["id"] != only:
                continue
            d = it["eq_delay"]
            x = it["mod"].render(start, n)
            if it["eq"] is not None:
                x = it["eq"](x)  # FIR group delay (1023 samples) is constant; irrelevant for ambience
            g = 10 ** (self.gain_db(it) / 20)
            out += x * g * self._adapt(start, n, 1.0 if it["is_bed"] else 0.5)
        return out


@lru_cache(maxsize=256)
def _module_psd_cached(mtype: str, params_key: str, seed: int, fs: int, seconds: float):
    import json
    params = json.loads(params_key)
    cls = MODULE_TYPES[mtype]
    mod = cls(fs, seed, params, seconds + 5)
    x = mod.render(0, int(seconds * fs))  # exactly the window that generation renders and evaluation analyses
    mono = x.mean(axis=1) if x.ndim == 2 else x
    f, p = welch_psd(mono, fs, seg_s=0.25)
    pl, pr = welch_psd(x[:, 0], fs, seg_s=0.25)[1], welch_psd(x[:, 1], fs, seg_s=0.25)[1]
    return f, 0.5 * (pl + pr), p


def module_psd(m: dict, fs: int, scene_seed: int, seconds: float = 30.0):
    """PSD of a module at 0 dB level over [0, seconds) of the SAME seeded audio the scene will render
    (average of L/R channel PSDs, units^2/Hz). Using the identical window makes the optimizer's level
    predictions match the rendered result (a short generic excerpt was off by up to 11 dB for gusty beds)."""
    import json
    params = dict(m.get("params", {}))
    params.setdefault("gust_seed", derive_seed(scene_seed, "gusts"))
    f, p_ch, _ = _module_psd_cached(m["type"], json.dumps(params, sort_keys=True),
                                    derive_seed(scene_seed, m["id"]), int(fs), float(seconds))
    return f, p_ch


def render_to_array(scene: Scene, n_total: int, chunk: int | None = None, progress=None) -> np.ndarray:
    chunk = chunk or scene.fs * 10
    out = np.zeros((n_total, 2), dtype=np.float64)
    pos = 0
    while pos < n_total:
        m = min(chunk, n_total - pos)
        out[pos:pos + m] = scene.render(pos, m)
        pos += m
        if progress:
            progress(pos / n_total)
    return out


def seamless_loop(x: np.ndarray, n_out: int, xfade: int) -> np.ndarray:
    """x must have n_out + xfade samples. Equal-power crossfade of the tail into the head."""
    if x.shape[0] < n_out + xfade:
        raise ValueError("need n_out + xfade samples")
    y = x[:n_out].copy()
    w = np.linspace(0, math.pi / 2, xfade)[:, None]
    y[:xfade] = x[:xfade] * np.sin(w) + x[n_out:n_out + xfade] * np.cos(w)
    return y
