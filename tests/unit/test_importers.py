import io

import numpy as np
import pytest
import soundfile as sf
from scipy import io as sio

from app.io import importers

FS = 48000


def mat_bytes(d, v73=False):
    if v73:
        import h5py
        buf = io.BytesIO()
        with h5py.File(buf, "w") as h:
            for k, v in d.items():
                h[k] = np.asarray(v).T
        return buf.getvalue()
    buf = io.BytesIO()
    sio.savemat(buf, d)
    return buf.getvalue()


def test_mat_v5_sig_fs_dist():
    sig = np.random.default_rng(0).normal(0, 0.5, (FS, 2))
    r = importers.load_mat(mat_bytes({"sig": sig, "fs": FS, "dist": 1.5, "line": "front", "units": "Pa"}))
    assert r["sig"].shape == (FS, 2) and r["fs"] == FS
    assert r["meta"]["dist"] == 1.5 and r["meta"]["line"] == "front"
    assert r["suggested_domain"]["domain"] == "PASCAL"


def test_mat_row_vector_and_time_vector():
    sig = np.sin(np.arange(1000) / 10.0)[None, :]
    t = (np.arange(1000) / 8000.0)[None, :]
    r = importers.load_mat(mat_bytes({"sig": sig, "t": t}))
    assert r["sig"].shape == (1000, 1) and r["fs"] == pytest.approx(8000)
    assert r["suggested_domain"]["domain"] == "DIGITAL_UNCALIBRATED"


def test_mat_v73():
    sig = np.random.default_rng(1).normal(0, 0.1, (5000, 1))
    r = importers.load_mat(mat_bytes({"sig": sig, "fs": np.array([[44100.0]])}, v73=True))
    assert r["format"].startswith("MAT v7.3")
    assert r["sig"].shape == (5000, 1) and r["fs"] == 44100


def test_mat_without_signal_is_user_error():
    with pytest.raises(importers.ImportErrorUser):
        importers.load_mat(mat_bytes({"fs": 48000}))


def test_audio_wav():
    buf = io.BytesIO()
    sf.write(buf, np.zeros((480, 2)), FS, format="WAV", subtype="PCM_16")
    r = importers.load_audio(buf.getvalue())
    assert r["sig"].shape == (480, 2) and r["fs"] == FS


def test_csv_octave_with_duplicates_and_missing():
    text = "Frequency (Hz),SPL (dB)\n63,70\n125,72\n250,75\n250,75\n500,\n1000,80\n2000,77\n4000,72\n8000,65\n"
    t = importers.load_table(text.encode(), "x.csv")
    s = t["suggested"]
    assert s["frequency_column"] == "Frequency (Hz)" and s["representation"] == "octave"
    spec = importers.table_to_spectrum(t["_df"], s["frequency_column"], "SPL (dB)")
    assert spec["f"] == [63, 125, 250, 1000, 2000, 4000, 8000]
    assert any("duplicated" in w for w in spec["warnings"]) and any("ignored" in w for w in spec["warnings"])


def test_xlsx_third_octave_lw_detection(tmp_path):
    import pandas as pd
    f = [100, 125, 160, 200, 250, 315, 400, 500]
    df = pd.DataFrame({"f [Hz]": f, "Lw dB": np.linspace(80, 90, len(f))})
    p = tmp_path / "t.xlsx"
    df.to_excel(p, index=False)
    t = importers.load_table(p.read_bytes(), "t.xlsx")
    assert t["suggested"]["representation"] == "third" and t["suggested"]["quantity"] == "Lw"


def test_a_weighted_table_is_unweighted():
    text = "f,dBA\n1000,80\n125,60\n"
    t = importers.load_table(text.encode(), "a.csv")
    assert t["suggested"]["a_weighted"]
    spec = importers.table_to_spectrum(t["_df"], "f", "dBA", "octave", a_weighted=True)
    assert spec["L"][1] == pytest.approx(80.0, abs=0.01)
    assert spec["L"][0] == pytest.approx(60 + 16.10, abs=0.05)  # A at exact 125.89 Hz


def test_continuous_detection():
    assert importers.detect_representation(np.linspace(20, 20000, 500)) == "continuous"
