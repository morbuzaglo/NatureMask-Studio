import numpy as np
import pytest

from app import engine
from app.optimization.optimizer import OptimizeRequest, adaptation_curve, optimize_masking
from app.synthesis.presets import build_scene_config
from app.synthesis.target_synth import demo_machine_spectrum

FS = 48000


def demo_req(kind, preset, **kw):
    fm, L, tones, pattern = demo_machine_spectrum(kind)
    meta, arr = engine.target_from_spectrum(fm, L, "third", tones=tones, pattern=pattern, provenance="SYNTHETIC")
    f, p = engine.target_psd(meta, arr, FS)
    return OptimizeRequest(f=f, target_psd=p, calibrated=True, scene_config=build_scene_config(preset), fs=FS,
                           seed=3, tonal_bands_hz=[t["f"] for t in tones], **kw), meta


def test_M6_masker_level_constraint_respected():
    req, _ = demo_req("drill", "riverside", max_masker_la=60.0)
    r = optimize_masking(req)
    assert r["levels"]["LA_masker"] <= 60.0 + 0.05


def test_M7_low_frequency_target_reported_infeasible():
    req, _ = demo_req("generator_lf", "forest_morning", max_masker_la=60.0)
    r = optimize_masking(req)
    assert r["remaining_audible"], "LF tones should remain audible under a tight masker limit"
    assert any(b["band_hz"] < 200 for b in r["remaining_audible"])
    assert any("Low-frequency" in n for n in r["notes"])


def test_objectives_trade_off():
    req_mask, _ = demo_req("grinder_hf", "meadow_summer", objective="max_masking")
    req_spl, _ = demo_req("grinder_hf", "meadow_summer", objective="min_added_spl")
    a = optimize_masking(req_mask)
    b = optimize_masking(req_spl)
    assert a["terms"]["masking_loss_db"] <= b["terms"]["masking_loss_db"] + 1e-6
    assert b["levels"]["delta_LA"] <= a["levels"]["delta_LA"] + 1e-6


def test_pareto_non_dominated():
    req, _ = demo_req("drill", "countryside_afternoon")
    r = optimize_masking(req, pareto=True)
    nd = r["pareto"]["non_dominated"]
    assert nd
    for p in nd:
        assert not any(q["masking_loss"] < p["masking_loss"] - 1e-9 and q["added_level"] < p["added_level"] - 1e-9
                       for q in r["pareto"]["points"])


def test_uncalibrated_units_label():
    req, _ = demo_req("fan", "riverside")
    req.calibrated = False
    req.target_psd = req.target_psd / (20e-6) ** 2 * 1e-8  # arbitrary digital scale
    r = optimize_masking(req)
    assert "relative" in r["levels"]["unit"]


def test_adaptation_curve_smooth_and_bounded():
    t = np.arange(0, 60, 0.5)
    la = np.where((t % 10) < 4, 80.0, 60.0)
    tt, g = adaptation_curve(t, la, depth_db=6, rate_hz=10)
    assert np.max(np.abs(g)) <= 6 + 1e-9
    assert np.max(np.abs(np.diff(g))) <= 3.0 / 10 + 1e-9  # slew limit 3 dB/s


def test_template_spectrum_hits_requested_la():
    from app.acoustics.bands import total_from_bands
    fm, L, tones = engine.template_spectrum("electric_drill", 78.0)
    from app.acoustics.levels import energy_sum, a_weighting_db
    total = energy_sum([total_from_bands(fm, L, "A")] + [t["level_db"] + float(a_weighting_db(t["f"])) for t in tones])
    assert total == pytest.approx(78.0, abs=0.01)
