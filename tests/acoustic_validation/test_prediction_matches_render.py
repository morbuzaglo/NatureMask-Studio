"""Regression: the optimizer's predicted soundscape level must match the rendered audio.

Found during the UI walkthrough (2026-10-20): predicted 78.5 dB(A), rendered 86.0 dB(A), because the
optimizer analysed a short generic excerpt of lognormal gust processes. Fixed by analysing the exact
seeded window that generation renders and by normalising gust energy.
"""
import numpy as np
import pytest

from app import engine
from app.acoustics.levels import P0
from app.generation import ANALYSIS_WINDOW_S, analysis_window_s
from app.dsp.spectral import welch_psd
from app.acoustics.bands import total_from_psd
from app.optimization.optimizer import OptimizeRequest, optimize_masking
from app.synthesis.presets import build_scene_config
from app.synthesis.scene import Scene, render_to_array
from app.synthesis.target_synth import demo_machine_spectrum
from app.synthesis.wind import gust_signal

FS = 48000


@pytest.mark.parametrize("preset,duration", [("countryside_afternoon", 60), ("mountain_wind", 45), ("rainy_woodland", 20),
                                              ("coastal_breeze", 30)])
def test_predicted_masker_level_matches_rendered(preset, duration):
    fm, L, tones, pattern = demo_machine_spectrum("drill")
    meta, arr = engine.target_from_spectrum(fm, L, "third", tones=tones, pattern=pattern, provenance="SYNTHETIC")
    f, p = engine.target_psd(meta, arr, FS)
    cfg = build_scene_config(preset)
    win = analysis_window_s(duration)
    r = optimize_masking(OptimizeRequest(f=f, target_psd=p, calibrated=True, scene_config=cfg, fs=FS, seed=1, analysis_s=win))
    sol = r["solution"]
    sc = Scene(cfg, FS, duration, 1, master_db=sol["master_db"], module_gains_db=sol["module_offsets_db"], bed_eq=sol["bed_eq_db"])
    x = render_to_array(sc, int(win * FS))
    fl, pl = welch_psd(x[:, 0], FS, 0.5)
    _, pr = welch_psd(x[:, 1], FS, 0.5)
    la = total_from_psd(fl, 0.5 * (pl + pr), P0, "A")
    assert la == pytest.approx(r["levels"]["LA_masker"], abs=0.75)


def test_gusts_independent_of_duration_and_unit_energy():
    a = gust_signal(7, "wind", 30, 1.0, 0.5)
    b = gust_signal(7, "wind", 600, 1.0, 0.5)
    assert np.array_equal(a, b[: len(a)])
    long = gust_signal(11, "wind", 20000, 1.0, 0.5)
    assert np.mean(long ** 2) == pytest.approx(1.0, rel=0.35)  # lognormal mean energy ~1 over long runs


def test_scene_prefix_independent_of_duration():
    cfg = build_scene_config("mountain_wind")
    x1 = render_to_array(Scene(cfg, FS, 15, 3), FS * 10)
    x2 = render_to_array(Scene(cfg, FS, 300, 3), FS * 10)
    assert np.max(np.abs(x1 - x2)) < 1e-9
