"""Deterministic, block-based generative audio core.

Every module renders fixed 1-second blocks. Randomness for block k comes from a generator seeded by
(module seed, k), and filter/oscillator state is carried from block to block. A render request of any
(start, n) is served by rendering blocks sequentially, so chunked rendering is bit-identical to a
one-shot render regardless of chunk size (tested).

Events (bird songs, bubbles, drops ...) that start in block k but extend beyond it are written to an
overlap-add tail buffer consumed by the following blocks.
"""
from __future__ import annotations

import hashlib
import math

import numpy as np
from scipy import signal


def derive_seed(*parts) -> int:
    h = hashlib.sha256("|".join(str(p) for p in parts).encode()).digest()
    return int.from_bytes(h[:8], "little") & ((1 << 63) - 1)


def ou_process(n: int, dt: float, theta: float, sigma: float, rng: np.random.Generator, x0: float = 0.0):
    """Ornstein-Uhlenbeck path (mean 0): exact discretisation. Stationary std = sigma."""
    a = math.exp(-theta * dt)
    s = sigma * math.sqrt(1 - a * a)
    z = rng.standard_normal(n)
    x = np.empty(n)
    prev = x0
    for i in range(n):  # n is a control-rate length (e.g. 100 per second) -> cheap
        prev = a * prev + s * z[i]
        x[i] = prev
    return x


def pan_gains(pan: float):
    """Constant-power pan, pan in [-1 (left), +1 (right)]."""
    th = (pan + 1) * math.pi / 4
    return math.cos(th), math.sin(th)


def raised_cosine(n: int):
    if n <= 1:
        return np.ones(max(n, 0))
    return 0.5 - 0.5 * np.cos(np.pi * np.arange(n) / (n - 1))


class StatefulSOS:
    """sosfilt with carried state (per channel)."""

    def __init__(self, sos, channels: int = 1):
        self.sos = np.asarray(sos)
        self.zi = np.zeros((self.sos.shape[0], 2, channels)) if channels > 1 else np.zeros((self.sos.shape[0], 2))

    def __call__(self, x):
        y, self.zi = signal.sosfilt(self.sos, x, axis=0, zi=self.zi)
        return y


class StatefulFIR:
    """FFT overlap-add FIR filtering with carried tail (block-size independent)."""

    def __init__(self, h, channels: int = 2):
        self.h = np.asarray(h, float)
        self.tail = np.zeros((len(self.h) - 1, channels))

    def __call__(self, x):
        y = signal.oaconvolve(x, self.h[:, None], mode="full", axes=0)
        n = x.shape[0]
        y[: len(self.tail)] += self.tail
        out = y[:n].copy()
        rest = y[n:]
        self.tail = rest
        return out


class Module:
    """Base class. Subclasses implement `_block(k, rng) -> (B, 2)` and may use `self.add_event`."""

    kind = "base"
    is_bed = False            # broadband bed (may receive EQ from the optimizer)
    tonal_fraction = 0.0      # 0 = noise-like, 1 = tonal (affects masking estimate)
    label = "Module"

    def __init__(self, fs: int, seed: int, params: dict | None = None, duration_s: float = 60.0):
        self.fs = int(fs)
        self.B = self.fs  # 1-second blocks
        self.seed = int(seed)
        self.params = dict(params or {})
        self.duration_s = float(duration_s)
        self._next_block = 0
        self._buf = np.zeros((0, 2))
        self._buf_start = 0
        self._tail = np.zeros((0, 2))
        self.setup()

    # -- hooks
    def setup(self):
        pass

    def _block(self, k: int, rng: np.random.Generator) -> np.ndarray:
        raise NotImplementedError

    # -- event overlap-add relative to the current block start
    def add_event(self, out: np.ndarray, offset: int, wave: np.ndarray):
        """Add `wave` (L,2) starting at `offset` samples inside the current block; overflow -> tail."""
        L = wave.shape[0]
        end = offset + L
        B = out.shape[0]
        if offset < B:
            k = min(end, B) - offset
            out[offset:offset + k] += wave[:k]
        if end > B:
            over = wave[max(0, B - offset):]
            start_in_tail = max(0, offset - B)
            need = start_in_tail + over.shape[0]
            if self._tail.shape[0] < need:
                self._tail = np.vstack([self._tail, np.zeros((need - self._tail.shape[0], 2))])
            self._tail[start_in_tail:start_in_tail + over.shape[0]] += over

    def _render_next_block(self) -> np.ndarray:
        k = self._next_block
        rng = np.random.default_rng(derive_seed(self.seed, self.kind, k))
        out = np.zeros((self.B, 2))
        if self._tail.shape[0]:
            m = min(self.B, self._tail.shape[0])
            out[:m] += self._tail[:m]
            self._tail = self._tail[m:]
        blk = self._block(k, rng)
        out += blk
        self._next_block += 1
        return out

    def reset(self):
        self._next_block = 0
        self._buf = np.zeros((0, 2))
        self._buf_start = 0
        self._tail = np.zeros((0, 2))
        self.setup()

    def render(self, start: int, n: int) -> np.ndarray:
        """Render samples [start, start+n). Sequential access is efficient; going backwards resets."""
        if start < self._buf_start:
            self.reset()
        while self._buf_start + self._buf.shape[0] < start + n:
            blk = self._render_next_block()
            self._buf = np.vstack([self._buf, blk]) if self._buf.size else blk
        i0 = start - self._buf_start
        out = self._buf[i0:i0 + n].copy()
        # drop consumed samples (keep from `start+n` onward)
        drop = (start + n) - self._buf_start
        drop_blocks = (drop // self.B) * self.B
        if drop_blocks > 0:
            self._buf = self._buf[drop_blocks:]
            self._buf_start += drop_blocks
        return out


def bandpass_sos(fs, lo, hi, order=2):
    hi = min(hi, 0.45 * fs)
    return signal.butter(order, [lo, hi], btype="bandpass", fs=fs, output="sos")


def lowpass_sos(fs, fc, order=2):
    return signal.butter(order, min(fc, 0.45 * fs), btype="lowpass", fs=fs, output="sos")


def highpass_sos(fs, fc, order=2):
    return signal.butter(order, fc, btype="highpass", fs=fs, output="sos")


def control_to_audio(ctrl: np.ndarray, k: int, B: int, ctrl_rate: int) -> np.ndarray:
    """Linear interpolation of a control signal (sampled at ctrl_rate) onto audio samples of block k."""
    t0 = k * ctrl_rate
    seg = ctrl[min(t0, len(ctrl) - 1): min(t0 + ctrl_rate + 1, len(ctrl))]
    if seg.size < ctrl_rate + 1:
        seg = np.concatenate([seg, np.full(ctrl_rate + 1 - seg.size, seg[-1] if seg.size else 0.0)])
    xp = np.arange(ctrl_rate + 1) * (B / ctrl_rate)
    return np.interp(np.arange(B), xp, seg)
