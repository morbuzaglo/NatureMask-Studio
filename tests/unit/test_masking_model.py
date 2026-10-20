import math

import numpy as np
import pytest

from app.acoustics.levels import P0
from app.psychoacoustics import auditory, masking

FS = 48000
F = np.linspace(0, FS / 2, 24001)


def white(level_db_per_hz):
    return np.full_like(F, P0 ** 2 * 10 ** (level_db_per_hz / 10))


def tone_psd(freq, level_db):
    p = np.zeros_like(F)
    i = int(np.argmin(abs(F - freq)))
    p[i] = P0 ** 2 * 10 ** (level_db / 10) / (F[1] - F[0])
    return p


def band_index(res, f):
    return int(np.argmin(abs(res["bands_hz"] - f)))


def test_erb_and_roex_bandwidth():
    assert float(auditory.erb_hz(1000)) == pytest.approx(132.639, abs=1e-3)
    w = auditory.roex_matrix(F, np.array([1000.0]))
    assert float(w.sum()) == pytest.approx(132.639, rel=0.01)


def test_M1_tone_at_threshold():
    # masker 30 dB/Hz white noise -> filter level 30 + 10log10(ERB at the band centre)
    res0 = masking.estimate(F, np.zeros_like(F), white(30), P0, True, fs=FS)
    i = band_index(res0, 1000)
    fc = res0["bands_hz"][i]
    lthr = 30 + 10 * math.log10(float(auditory.erb_hz(fc))) - 4
    res = masking.estimate(F, tone_psd(fc, lthr), white(30), P0, True, fs=FS)
    assert res["margin"][i] == pytest.approx(0.0, abs=0.6)  # roex weight at the bin nearest fc ~ 1


def test_M2_raising_masker_lowers_margin_by_same_amount():
    tgt = white(20)
    r1 = masking.estimate(F, tgt, white(30), P0, True, fs=FS)
    r2 = masking.estimate(F, tgt, white(40), P0, True, fs=FS)
    mid = (r1["bands_hz"] > 200) & (r1["bands_hz"] < 8000)
    assert np.allclose(r1["margin"][mid] - r2["margin"][mid], 10.0, atol=0.05)
    assert r2["prominence_index_db"] < r1["prominence_index_db"]


def test_target_far_below_threshold():
    r = masking.estimate(F, white(-10), white(30), P0, True, fs=FS)
    assert r["prominence_index_db"] < -25
    assert r["audible_band_count"] == 0


def test_M5_spectral_overlap_required():
    tgt = tone_psd(200, 60)
    hf = np.where((F > 4000) & (F < 8000), P0 ** 2 * 10 ** (40 / 10), 0.0)
    lf = np.where((F > 100) & (F < 400), P0 ** 2 * 10 ** (40 / 10), 0.0)
    r_hf = masking.estimate(F, tgt, hf, P0, True, fs=FS)
    r_lf = masking.estimate(F, tgt, lf, P0, True, fs=FS)
    i = band_index(r_hf, 200)
    assert r_hf["margin"][i] > 30          # HF insects cannot mask a 200 Hz tone
    assert r_lf["margin"][i] < r_hf["margin"][i] - 30


def test_M8_monotonic_in_masker_gain():
    tgt = tone_psd(2400, 60) + white(10)
    pis = [masking.estimate(F, tgt, white(L), P0, True, fs=FS)["prominence_index_db"] for L in range(0, 60, 5)]
    assert all(b <= a + 1e-9 for a, b in zip(pis, pis[1:]))


def test_tonal_masker_is_weaker():
    tgt = white(25)
    r = masking.estimate(F, tgt, white(30), P0, True, fs=FS)
    rt = masking.estimate(F, tgt, white(30), P0, True, fs=FS, masker_tonal_fraction=np.ones(len(r["bands_hz"])))
    mid = (r["bands_hz"] > 200) & (r["bands_hz"] < 8000)
    assert np.allclose(rt["margin"][mid] - r["margin"][mid], 10.0, atol=0.05)
    assert rt["prominence_index_db"] > r["prominence_index_db"]
