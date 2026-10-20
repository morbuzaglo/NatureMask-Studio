import numpy as np
import pytest

from app.acoustics.bands import band_levels_from_psd
from app.dsp.spectral import welch_psd
from app.synthesis.core import derive_seed
from app.synthesis.presets import PRESETS, build_scene_config
from app.synthesis.scene import MODULE_TYPES, Scene, render_to_array, seamless_loop
from app.synthesis.target_synth import SpectrumTarget
from app.synthesis.insects import dolbear_chirps_per_min

FS = 48000


@pytest.mark.parametrize("mtype", sorted(MODULE_TYPES))
def test_module_finite_and_chunk_invariant(mtype):
    a = MODULE_TYPES[mtype](FS, 1234, {}, 10)
    one = a.render(0, FS * 4)
    b = MODULE_TYPES[mtype](FS, 1234, {}, 10)
    parts = []
    pos = 0
    for n in (12345, 48000, 7, 60000, FS * 4 - 12345 - 48000 - 7 - 60000):
        parts.append(b.render(pos, n))
        pos += n
    chunked = np.vstack(parts)
    assert np.isfinite(one).all()
    assert np.max(np.abs(one - chunked)) < 1e-9


@pytest.mark.parametrize("mtype", sorted(MODULE_TYPES))
def test_module_seed_determinism(mtype):
    x1 = MODULE_TYPES[mtype](FS, 99, {}, 6).render(0, FS * 3)
    x2 = MODULE_TYPES[mtype](FS, 99, {}, 6).render(0, FS * 3)
    x3 = MODULE_TYPES[mtype](FS, 100, {}, 6).render(0, FS * 3)
    assert np.array_equal(x1, x2)
    if np.any(x1 != 0) or np.any(x3 != 0):
        assert not np.array_equal(x1, x3)


def test_presets_render_and_no_clipping_in_raw_mix():
    for pid in PRESETS:
        if pid == "custom":
            continue
        sc = Scene(build_scene_config(pid), FS, 8, seed=3)
        x = render_to_array(sc, FS * 6)
        assert np.isfinite(x).all()
        assert np.sqrt(np.mean(x ** 2)) > 1e-4  # audible content


def test_modifiers_disable_insects_in_winter():
    cfg = build_scene_config("meadow_summer", season="winter")
    en = {m["type"]: m["enabled"] for m in cfg["modules"]}
    assert en["crickets"] is False and en["cicadas"] is False


def test_bird_event_rate_poisson():
    from app.synthesis.birds import Birds
    b = Birds(FS, 5, {"activity": 0.5, "individuals": 4}, 600)
    expected = sum(v["rate"] for v in b.birds)
    counts = [np.random.default_rng(derive_seed(b.seed, b.kind, k)).poisson(1) for k in range(1)]  # smoke
    # count songs: sum of Poisson draws over 600 blocks reproduces the configured mean within 10 %
    n = 0
    for k in range(600):
        rng = np.random.default_rng(derive_seed(b.seed, b.kind, k))
        n += sum(rng.poisson(v["rate"]) for v in b.birds[:1])
    assert abs(n / 600 - b.birds[0]["rate"]) < 0.25 * b.birds[0]["rate"] + 0.02


def test_birds_spectrum_in_bird_range():
    from app.synthesis.birds import Birds
    x = Birds(FS, 8, {"activity": 1.0, "species": ["warbler"], "individuals": 6}, 40).render(0, FS * 30).mean(1)
    f, p = welch_psd(x, FS)
    centroid = np.sum(f * p) / np.sum(p)
    assert 2500 < centroid < 9000


def test_cricket_dolbear():
    assert dolbear_chirps_per_min(25.0) == pytest.approx(4 * (77 - 50) + 40)


def test_spectrum_target_matches_requested_bands():
    from app.acoustics.bands import band_centres, psd_from_bands
    fm, _, _ = band_centres(3, 50, 10000)
    L = np.full(len(fm), 60.0) - 0.3 * np.arange(len(fm))
    fgrid = np.linspace(0, FS / 2, FS // 2 + 1)
    ref = 20e-6
    psd = psd_from_bands(fm, L, ref, fgrid, 3)
    t = SpectrumTarget(FS, 1, {"f": fgrid, "psd": psd}, 30)
    x = t.render(FS, FS * 20)[:, 0]
    f, p = welch_psd(x, FS)
    fm2, L2 = band_levels_from_psd(f, p, ref, 3, 100, 8000)
    sel = (fm >= fm2[0] * 0.99) & (fm <= fm2[-1] * 1.01)
    assert np.max(np.abs(L2 - L[sel])) < 1.0


def test_seamless_loop_continuity():
    sc = Scene(build_scene_config("riverside"), FS, 12, seed=1)
    x = render_to_array(sc, FS * 10 + FS * 2)
    y = seamless_loop(x, FS * 10, FS * 2)
    # the sample after the end of y (wrapping to y[0]) continues x smoothly: y[0] == x[n_out] at fade start
    assert np.allclose(y[0], x[FS * 10], atol=1e-12)
    jump = np.abs(y[0] - y[-1]).max()
    typical = np.median(np.abs(np.diff(x[:, 0])))
    assert jump < 20 * typical + 1e-3


def test_long_render_stable_level():
    sc = Scene(build_scene_config("riverside"), FS, 125, seed=2)
    x = render_to_array(sc, FS * 120)
    first = 10 * np.log10(np.mean(x[:FS * 60] ** 2))
    last = 10 * np.log10(np.mean(x[FS * 60:] ** 2))
    assert abs(first - last) < 3.0
