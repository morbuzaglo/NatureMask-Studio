"""End-to-end workflow through the HTTP API (FastAPI TestClient)."""
import io
import os
import shutil
import time

import numpy as np
import pytest
import soundfile as sf
from scipy import io as sio

os.environ["NATUREMASK_DATA_DIR"] = os.path.join(os.path.dirname(__file__), "..", "..", "data", "_itest")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

FS = 48000
client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def clean_data():
    d = os.environ["NATUREMASK_DATA_DIR"]
    shutil.rmtree(d, ignore_errors=True)
    yield
    shutil.rmtree(d, ignore_errors=True)


def wait(job_id, timeout=600):
    t0 = time.time()
    while time.time() - t0 < timeout:
        j = client.get(f"/api/jobs/{job_id}").json()
        if j["status"] in ("done", "error"):
            assert j["status"] == "done", j.get("error")
            return j
        time.sleep(0.3)
    raise TimeoutError(job_id)


def new_project(name, **settings):
    p = client.post("/api/projects", json={"name": name}).json()
    s = {"duration_s": 12, "preview_s": 12}
    s.update(settings)
    client.patch(f"/api/projects/{p['id']}", json={"settings": s})
    return p["id"]


def run_pipeline(pid, preset="countryside_afternoon", formats=("wav16", "wav24", "wav32f", "mat", "csv", "json", "report"),
                 mat_domain="digital"):
    assert client.put(f"/api/projects/{pid}/scene", json={"preset": preset}).status_code == 200
    r = client.post(f"/api/projects/{pid}/optimize", json={"objective": "balanced"})
    assert r.status_code == 200, r.text
    opt = r.json()
    j = wait(client.post(f"/api/projects/{pid}/generate").json()["job"])
    ev = client.get(f"/api/projects/{pid}/evaluation").json()["evaluation"]
    for s in ("target", "masker", "mix"):
        a = client.get(f"/api/projects/{pid}/audio/{s}")
        assert a.status_code == 200
        x, fs = sf.read(io.BytesIO(a.content))
        assert fs == FS and np.isfinite(x).all() and np.max(np.abs(x)) <= 1.0
    ex = wait(client.post(f"/api/projects/{pid}/export", json={"formats": list(formats), "stream": "masker",
                                                               "mat_signal_domain": mat_domain}).json()["job"])
    files = ex["result"]["files"]
    assert all(f["valid"] for f in files), files
    return opt, ev, files


def test_example4_manual_octave_spectrum_full_workflow():
    pid = new_project("Example 4 octave")
    body = {"f": [63, 125, 250, 500, 1000, 2000, 4000, 8000], "L": [70, 72, 75, 78, 80, 77, 72, 65],
            "representation": "octave", "quantity": "Lp", "name": "Manual octave spectrum"}
    r = client.post(f"/api/projects/{pid}/target/spectrum", json=body)
    assert r.status_code == 200, r.text
    an = r.json()["analysis"]
    assert an["levels"]["LZeq"] == pytest.approx(84.62, abs=0.15)
    assert an["levels"]["LAeq"] == pytest.approx(83.48, abs=0.15)
    assert "SYNTHETIC" in an["synthetic_note"]
    opt, ev, files = run_pipeline(pid)
    # evaluation is computed from the rendered masker; it must agree with the optimizer prediction (L_A)
    assert ev["masker"]["LAeq"] == pytest.approx(opt["levels"]["LA_masker"], abs=1.5)
    assert ev["target"]["LAeq"] == pytest.approx(83.48, abs=0.3)
    # reload exports
    d = os.path.join(os.environ["NATUREMASK_DATA_DIR"], "projects", pid, "exports")
    mat = [f for f in files if f["format"] == "mat"][0]
    m = sio.loadmat(os.path.join(d, mat["file"]))
    assert m["sig"].shape == (12 * FS, 2) and float(m["fs"].ravel()[0]) == FS and m["t"].shape == (12 * FS, 1)
    assert "L_Aeq" in m and "Lp_third" in m and m["f_oct"].shape[1] == 1
    md = m["metadata"][0, 0]
    assert str(md["calibration_status"][0]) == "calibrated"
    # the MAT L_Aeq is the design level of the masker: consistent with evaluation within 0.3 dB
    assert float(m["L_Aeq"].ravel()[0]) == pytest.approx(ev["masker"]["LAeq"], abs=0.3)
    w24 = [f for f in files if f["format"] == "wav24"][0]
    x, fs = sf.read(os.path.join(d, w24["file"]))
    assert fs == FS and x.shape == (12 * FS, 2)
    # WAV * pa_per_full_scale reproduces the Pa-domain signal level
    pa_per_fs = float(md["pa_per_full_scale"].ravel()[0])
    from app.acoustics.levels import P0
    lz_wav = 20 * np.log10(np.sqrt(np.mean((x * pa_per_fs) ** 2)) / P0)
    assert lz_wav == pytest.approx(10 * np.log10(np.mean(10 ** (np.array([ev["masker"]["LZeq"]]) / 10))), abs=0.6)
    # project reopen
    p = client.get(f"/api/projects/{pid}").json()
    assert p["render"] and p["optimization"] and p["scene"]["preset"] == "countryside_afternoon"


def test_example5_mat_import_export_uncalibrated_never_spl():
    pid = new_project("Example 5 MAT")
    rng = np.random.default_rng(0)
    t = np.arange(FS * 6) / FS
    sig = 0.05 * rng.standard_normal(len(t)) + 0.2 * np.sin(2 * np.pi * 2400 * t)  # normalised digital samples
    buf = io.BytesIO()
    sio.savemat(buf, {"sig": sig[:, None], "fs": float(FS), "dist": 1.0, "line": "front"})
    up = client.post(f"/api/projects/{pid}/upload", files={"file": ("drill.mat", buf.getvalue())}).json()
    assert up["kind"] == "signal" and up["suggested_domain"]["domain"] == "DIGITAL_UNCALIBRATED"
    r = client.post(f"/api/projects/{pid}/target/signal", json={"domain": "DIGITAL_UNCALIBRATED", "channel": 0})
    assert r.status_code == 200, r.text
    an = r.json()["analysis"]
    assert "relative" in an["level_unit"]
    assert any(abs(tn["frequency_hz"] - 2400) < 10 for tn in an["tones"])
    opt, ev, files = run_pipeline(pid, preset="meadow_summer", formats=("wav24", "mat"))
    d = os.path.join(os.environ["NATUREMASK_DATA_DIR"], "projects", pid, "exports")
    m = sio.loadmat(os.path.join(d, [f for f in files if f["format"] == "mat"][0]["file"]))
    assert "L_Aeq" not in m and "Lp_third" not in m  # never fabricate SPL for uncalibrated designs
    assert "Lrel_Aeq" in m
    assert str(m["metadata"][0, 0]["calibration_status"][0]) == "uncalibrated"
    # pressure export must be refused
    r = client.post(f"/api/projects/{pid}/export", json={"formats": ["mat"], "mat_signal_domain": "pascal"})
    assert r.status_code == 400


def test_calibrated_pa_recording_and_lw_input():
    pid = new_project("Pa recording")
    rng = np.random.default_rng(1)
    sig = 0.6 * rng.standard_normal(FS * 5)  # 0.6 Pa rms -> 89.5 dB
    buf = io.BytesIO()
    sio.savemat(buf, {"sig": sig, "fs": FS, "units": "Pa"})
    up = client.post(f"/api/projects/{pid}/upload", files={"file": ("pa.mat", buf.getvalue())}).json()
    assert up["suggested_domain"]["domain"] == "PASCAL"
    an = client.post(f"/api/projects/{pid}/target/signal", json={"domain": "PASCAL"}).json()["analysis"]
    assert an["levels"]["LZeq"] == pytest.approx(20 * np.log10(0.6 / 20e-6), abs=0.1)
    # Lw spectrum without distance is refused; with distance it converts
    body = {"f": [125, 250, 500, 1000, 2000, 4000], "L": [95, 97, 99, 100, 98, 94], "representation": "octave", "quantity": "Lw"}
    assert client.post(f"/api/projects/{pid}/target/spectrum", json=body).status_code == 400
    body["distance_m"] = 5.0
    r = client.post(f"/api/projects/{pid}/target/spectrum", json=body).json()
    assert r["target"]["provenance"] == "ESTIMATED_FROM_LW"
    # 1 kHz octave: 100 - 20log10(5) - 7.98 = 78.04
    oc = r["analysis"]["octave"]
    i = oc["labels"].index("1k")
    assert oc["L"][i] == pytest.approx(78.04, abs=0.2)


def test_csv_table_flow_and_manual_template():
    pid = new_project("Table")
    csv = "Frequency (Hz),SPL (dB)\n100,60\n125,62\n160,63\n200,65\n250,66\n315,66\n400,65\n500,64\n"
    t = client.post(f"/api/projects/{pid}/upload", files={"file": ("t.csv", csv.encode())}).json()
    assert t["kind"] == "table" and t["suggested"]["representation"] == "third"
    r = client.post(f"/api/projects/{pid}/target/table", json={"frequency_column": "Frequency (Hz)", "level_column": "SPL (dB)"})
    assert r.status_code == 200, r.text
    r = client.post(f"/api/projects/{pid}/target/manual", json={"la": 78, "template": "electric_drill"}).json()
    assert r["target"]["provenance"] == "ESTIMATED_FROM_TEMPLATE"
    assert r["analysis"]["levels"]["LAeq"] == pytest.approx(78.0, abs=0.3)


def test_errors_are_user_friendly():
    pid = new_project("Errors")
    r = client.post(f"/api/projects/{pid}/upload", files={"file": ("x.mat", b"not a mat file")})
    assert r.status_code == 400 and "MATLAB" in r.json()["detail"]
    assert client.post(f"/api/projects/{pid}/optimize", json={}).status_code == 400
    assert client.patch(f"/api/projects/{pid}", json={"settings": {"duration_s": 5}}).status_code == 400


def test_lp_distance_correction():
    pid = new_project("Distance")
    body = {"f": [500, 1000, 2000], "L": [80, 80, 80], "representation": "octave", "quantity": "Lp",
            "measured_at_m": 1.0, "distance_m": 4.0}
    r = client.post(f"/api/projects/{pid}/target/spectrum", json=body).json()
    assert r["target"]["provenance"] == "ESTIMATED_DISTANCE_CORRECTED"
    oc = r["analysis"]["octave"]
    assert oc["L"][oc["labels"].index("1k")] == pytest.approx(80 - 12.04, abs=0.15)
