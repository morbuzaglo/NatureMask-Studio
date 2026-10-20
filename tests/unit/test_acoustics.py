import math

import numpy as np
import pytest
from scipy import signal

from app.acoustics import bands, levels, propagation
from app.dsp import spectral

P0 = levels.P0
FS = 48000


def sine(f, amp, dur=2.0, fs=FS):
    t = np.arange(int(dur * fs)) / fs
    return amp * np.sin(2 * np.pi * f * t)


def test_rms_and_spl():
    assert levels.spl(sine(1000, 1.0), P0) == pytest.approx(90.969, abs=0.01)
    assert levels.spl(sine(1000, math.sqrt(2)), P0) == pytest.approx(93.979, abs=0.01)


def test_energy_sum():
    assert levels.energy_sum([80, 80]) == pytest.approx(83.0103, abs=1e-3)
    assert levels.energy_sum([80, 70]) == pytest.approx(80.4139, abs=1e-3)
    assert levels.energy_sum([60] * 10) == pytest.approx(70.0, abs=1e-9)
    assert levels.energy_difference(83.0103, 80) == pytest.approx(80.0, abs=1e-3)


@pytest.mark.parametrize("n,a", [(-15, -39.4), (-12, -26.2), (-9, -16.1), (-6, -8.6), (-3, -3.2), (0, 0.0),
                                 (3, 1.2), (6, 1.0), (9, -1.1), (12, -6.6)])
def test_a_weighting_table(n, a):
    assert float(levels.a_weighting_db(1000 * 10 ** (n / 10))) == pytest.approx(a, abs=0.1)


def test_bilinear_a_filter_warping_is_documented():
    # plain bilinear IIR deviates ~1.2 dB at 10 kHz (fs=48k) -> reason we use the FIR
    _, h = signal.sosfreqz(levels.weighting_sos("A", FS), worN=[10000.0], fs=FS)
    assert 0.8 < abs(20 * np.log10(abs(h[0])) - float(levels.a_weighting_db(10000))) < 1.6


@pytest.mark.parametrize("kind", ["A", "C"])
def test_fir_weighting_matches_analytic(kind):
    h = levels.weighting_fir(kind, FS)
    f = np.array([31.62, 63.1, 100, 1000, 4000, 10000.0, 16000])
    _, H = signal.freqz(h, worN=f, fs=FS)
    err = 20 * np.log10(np.abs(H)) - levels.weighting_db(f, kind)
    assert np.max(np.abs(err)) < 0.2


def test_time_domain_laeq_of_tone():
    x = sine(100, math.sqrt(2) * 1.0, 3.0)  # 93.98 dB at 100 Hz, A(100) = -19.14
    la = levels.spl(levels.apply_weighting(x, FS, "A")[FS // 2:], P0)
    assert la == pytest.approx(93.979 - 19.145, abs=0.3)


def test_band_definitions():
    fm, lo, hi = bands.band_centres(1, 31.5, 16000)
    assert len(fm) == 10 and fm[2] == pytest.approx(125.89, abs=0.01)
    fm3, _, _ = bands.band_centres(3, 20, 20000)
    assert len(fm3) == 31
    assert bands.nominal_label(fm3[0]) == "20" and bands.nominal_label(fm3[-1]) == "20k"


def test_parseval_and_white_noise_bands():
    rng = np.random.default_rng(3)
    sigma = 0.2
    x = rng.normal(0, sigma, FS * 20)
    f, p = spectral.welch_psd(x, FS)
    assert np.sum(p) * (f[1] - f[0]) == pytest.approx(sigma ** 2, rel=0.03)
    fm, L = bands.band_levels_from_psd(f, p, 1.0, 3, 100, 10000)
    expected = 10 * np.log10(sigma ** 2 / (FS / 2)) + 10 * np.log10(fm * (bands.G10 ** (1 / 6) - bands.G10 ** (-1 / 6)))
    assert np.max(np.abs(L - expected)) < 0.3


def test_tone_lands_in_its_band():
    x = sine(1000, math.sqrt(2), 4.0)
    f, p = spectral.welch_psd(x, FS)
    fm, L = bands.band_levels_from_psd(f, p, P0, 3)
    i = int(np.argmin(abs(fm - 1000)))
    assert L[i] == pytest.approx(93.979, abs=0.05)
    assert bands.total_from_psd(f, p, P0, "Z") == pytest.approx(93.979, abs=0.05)


def test_thirds_octaves_conversions():
    f3, _, _ = bands.band_centres(3, 31.5, 16000)
    L3 = np.full(len(f3), 60.0)
    fo, Lo = bands.thirds_to_octaves(f3, L3)
    assert np.allclose(Lo, 64.771, atol=0.01)
    fo2, _, _ = bands.band_centres(1, 63, 8000)
    Lo2 = np.array([70, 72, 75, 78, 80, 77, 72, 65.0])
    ft, Lt = bands.octaves_to_thirds(fo2, Lo2)
    fo3, Lo3 = bands.thirds_to_octaves(ft, Lt)
    assert np.allclose(Lo3, Lo2, atol=1e-6)  # energy preserved per octave


def test_octave_example_totals():
    fo, _, _ = bands.band_centres(1, 63, 8000)
    L = np.array([70, 72, 75, 78, 80, 77, 72, 65.0])
    assert bands.total_from_bands(fo, L, "Z") == pytest.approx(84.62, abs=0.01)
    assert bands.total_from_bands(fo, L, "A") == pytest.approx(83.48, abs=0.01)


def test_psd_from_bands_preserves_band_levels():
    fo, _, _ = bands.band_centres(3, 50, 10000)
    L = 60 + 5 * np.sin(np.arange(len(fo)))
    fgrid = np.linspace(0, 24000, 24001)
    psd = bands.psd_from_bands(fo, L, P0, fgrid, 3)
    fm, L2 = bands.band_levels_from_psd(fgrid, psd, P0, 3, 50, 10000)
    assert np.max(np.abs(L2 - L)) < 0.05


def test_lw_to_lp_and_back():
    fo, _, _ = bands.band_centres(1, 63, 8000)
    lw = np.full(len(fo), 100.0)
    lp, info = propagation.lw_to_lp(fo, lw, 5.0, "hemispherical")
    assert lp[0] == pytest.approx(78.04, abs=0.01)
    assert np.allclose(propagation.lp_to_lw(fo, lp, 5.0, "hemispherical"), lw)
    lpf, _ = propagation.lw_to_lp(fo, lw, 1.0, "free")
    assert lpf[0] == pytest.approx(100 - 10.99, abs=0.01)


def test_air_absorption_iso9613():
    for n, a in [(0, 5.0), (6, 22.9), (9, 76.6)]:
        f = 1000 * 10 ** (n / 10)
        assert float(propagation.atmospheric_absorption_db_per_m(f, 20, 70)) * 1000 == pytest.approx(a, rel=0.03)


def test_tone_detection_prominent_whine():
    rng = np.random.default_rng(0)
    x = rng.normal(0, 0.05, FS * 4) + sine(2400, 0.2, 4.0)
    f, p = spectral.welch_psd(x, FS, seg_s=0.5)
    tones = spectral.find_tones(f, p, 1.0)
    assert tones and abs(tones[0]["frequency_hz"] - 2400) < 5 and tones[0]["prominent"]


def test_temporal_classification():
    t = np.arange(400) * 0.125
    steady = np.full(400, 70.0) + np.random.default_rng(1).normal(0, 0.5, 400)
    inter = np.where((t % 4) < 1.0, 85.0, 50.0)
    assert spectral.temporal_character(steady)["class"] == "stationary"
    assert spectral.temporal_character(inter)["class"] == "intermittent"
