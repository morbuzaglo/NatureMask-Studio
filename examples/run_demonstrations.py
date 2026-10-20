"""Run the five required demonstration cases through the real API and write
docs/validation/demonstration-results.md. All machine targets are SYNTHETIC (clearly labelled).

    .venv\\Scripts\\python.exe examples\\run_demonstrations.py
"""
import io
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))
os.environ["NATUREMASK_DATA_DIR"] = os.path.join(ROOT, "data", "demos")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

c = TestClient(app)
DUR = 30


def wait(j):
    while True:
        r = c.get(f"/api/jobs/{j}").json()
        if r["status"] in ("done", "error"):
            assert r["status"] == "done", r["error"]
            return r["result"]
        time.sleep(0.3)


def project(name, target_call):
    pid = c.post("/api/projects", json={"name": name}).json()["id"]
    c.patch(f"/api/projects/{pid}", json={"settings": {"duration_s": DUR, "preview_s": DUR}})
    r = target_call(pid)
    assert r.status_code == 200, r.text
    return pid, r.json()["analysis"]


def run(pid, preset, objective, cap=3.0, generate=True):
    c.put(f"/api/projects/{pid}/scene", json={"preset": preset})
    o = c.post(f"/api/projects/{pid}/optimize", json={"objective": objective, "masker_cap_rel_db": cap}).json()
    row = {"preset": preset, "objective": objective, "cap": cap, "LA_target": o["levels"]["LA_target"],
           "LA_masker": o["levels"]["LA_masker"], "dLA": o["levels"]["delta_LA"], "PI_pred": o["prominence_index_db"],
           "aud": f'{o["audible_band_count"]}/{o["relevant_band_count"]}', "notes": o["notes"],
           "worst": o["remaining_audible"][:2]}
    if generate:
        wait(c.post(f"/api/projects/{pid}/generate").json()["job"])
        ev = c.get(f"/api/projects/{pid}/evaluation").json()["evaluation"]
        row.update({"LA_masker_rendered": ev["masker"]["LAeq"], "PI_eval": ev["prominence_index_db"], "dLA_eval": ev["delta_LA"]})
    return row


def fmt_row(r):
    cap = "none" if r["cap"] is None else f'+{r["cap"]:.0f}'
    ren = f'{r.get("LA_masker_rendered", float("nan")):.1f}' if "LA_masker_rendered" in r else "—"
    pie = f'{r["PI_eval"]:+.1f}' if "PI_eval" in r else "—"
    return (f'| {r["preset"]} | {r["objective"]} | {cap} | {r["LA_target"]:.1f} | {r["LA_masker"]:.1f} | {ren} | '
            f'{r["dLA"]:+.1f} | {r["PI_pred"]:+.1f} | {pie} | {r["aud"]} |')


HDR = ("| Environment | Objective | Cap (dB) | L_A machine | L_A soundscape (pred.) | (rendered) | ΔL_A | PI pred. | PI eval. | bands above goal |\n"
       "|---|---|---|---|---|---|---|---|---|---|")


def main():
    out = ["# Demonstration results", "",
           f"Generated {time.strftime('%Y-%m-%d %H:%M')} by `examples/run_demonstrations.py` (duration {DUR} s, 48 kHz, seed 1).",
           "All machine targets are **synthetic** engineering shapes, not measurements. Levels in dB(A) re 20 µPa at the listener.",
           "PI = prominence index of NM-PSM v1 (model index; 0 dB ≈ at estimated threshold in one band; not a probability).", ""]
    # Example 1
    pid, an = project("Example 1 — electric drill", lambda p: c.post(f"/api/projects/{p}/target/demo", json={"kind": "drill"}))
    rows = [run(pid, "countryside_afternoon", "balanced"), run(pid, "forest_morning", "balanced"),
            run(pid, "countryside_afternoon", "min_added_spl"), run(pid, "countryside_afternoon", "max_masking", cap=None, generate=False)]
    out += ["## Example 1 — Electric drill (synthetic: broadband 1–4 kHz, 2.4 kHz whine, 120 Hz hum, intermittent)", "", HDR,
            *[fmt_row(r) for r in rows], "",
            "Reading: with the default cap the soundscape partially masks the drill (+3 dB above the machine, ≈ +5 dB total). "
            "The 2.4 kHz whine remains the most audible component. Full masking would need the soundscape ≈ 15 dB above the "
            "machine — not a sensible design.", ""]
    # Example 2
    pid, an = project("Example 2 — high-frequency machine", lambda p: c.post(f"/api/projects/{p}/target/demo", json={"kind": "grinder_hf"}))
    rows = [run(pid, "meadow_summer", "balanced"), run(pid, "forest_night", "balanced"), run(pid, "meadow_summer", "min_added_spl")]
    out += ["## Example 2 — High-frequency mechanical noise (synthetic: 4–10 kHz, 6.3 kHz tone)", "", HDR, *[fmt_row(r) for r in rows], "",
            "Reading: insect textures (cicadas, crickets) put energy in the target's bands. Masking is partial at equal "
            "level; insects are partly tonal so they mask noise less efficiently than a broadband bed (modelled by K_eff).", ""]
    # Example 3
    pid, an = project("Example 3 — low-frequency generator", lambda p: c.post(f"/api/projects/{p}/target/demo", json={"kind": "generator_lf"}))
    rows = [run(pid, "mountain_wind", "balanced"), run(pid, "waterfall_glade", "balanced"), run(pid, "coastal_breeze", "balanced"),
            run(pid, "waterfall_glade", "max_masking", cap=None, generate=False)]
    notes = sorted({n for r in rows for n in r["notes"]})
    out += ["## Example 3 — Low-frequency machine (synthetic generator: 50/100/150 Hz harmonics)", "", HDR, *[fmt_row(r) for r in rows], "",
            "App notes: " + " ".join(f"“{n}”" for n in notes), "",
            "Reading: **natural-sound masking is expected to be ineffective here.** Even unconstrained, the low harmonics need "
            "a soundscape >10 dB louder than the generator; the remaining-audible list is dominated by bands < 200 Hz.", ""]
    # Example 4
    body = {"f": [63, 125, 250, 500, 1000, 2000, 4000, 8000], "L": [70, 72, 75, 78, 80, 77, 72, 65], "representation": "octave",
            "name": "Manual octave spectrum"}
    pid, an = project("Example 4 — octave spectrum", lambda p: c.post(f"/api/projects/{p}/target/spectrum", json=body))
    rows = [run(pid, "riverside", "balanced"), run(pid, "meadow_summer", "balanced")]
    out += ["## Example 4 — Manually defined octave spectrum (63 Hz–8 kHz: 70, 72, 75, 78, 80, 77, 72, 65 dB)", "",
            f"Computed from the bands: L_Z = {an['levels']['LZeq']:.2f} dB, L_A = {an['levels']['LAeq']:.2f} dB "
            "(hand calculation 84.62 / 83.48 dB). Audio of the target is a synthetic approximation.", "", HDR, *[fmt_row(r) for r in rows], ""]
    # Example 5
    raw = open(os.path.join(ROOT, "examples", "sample-noise", "synthetic_drill_Pa.mat"), "rb").read()
    pid = c.post("/api/projects", json={"name": "Example 5 — MATLAB round trip"}).json()["id"]
    c.patch(f"/api/projects/{pid}", json={"settings": {"duration_s": DUR, "preview_s": DUR}})
    up = c.post(f"/api/projects/{pid}/upload", files={"file": ("synthetic_drill_Pa.mat", raw)}).json()
    an = c.post(f"/api/projects/{pid}/target/signal", json={"domain": "PASCAL"}).json()["analysis"]
    r5 = run(pid, "countryside_afternoon", "balanced")
    files = wait(c.post(f"/api/projects/{pid}/export", json={"formats": ["wav16", "wav24", "wav32f", "mat", "csv", "report"],
                                                             "mat_signal_domain": "pascal"}).json()["job"])["files"]
    out += ["## Example 5 — MATLAB import and export", "",
            f"Input `examples/sample-noise/synthetic_drill_Pa.mat` ({up['format']}, sig {up['samples']}×{up['channels']}, fs {up['fs']:.0f} Hz, "
            f"domain suggested: {up['suggested_domain']['domain']} — {up['suggested_domain']['reason']}). "
            f"Analysis: L_Aeq {an['levels']['LAeq']:.1f} dB, temporal class {an['temporal']['class']}, tones "
            f"{', '.join(f'{t['frequency_hz']:.0f} Hz' for t in an['tones'][:3])}.", "", HDR, fmt_row(r5), "",
            "Exports (each re-read and validated):", ""]
    out += [f"- `{f['file']}` — {f['format']} — valid: {f['valid']}" for f in files]
    out += ["", "MATLAB R2021b `load` verification: see `docs/validation/matlab-verification.md`.", ""]
    path = os.path.join(ROOT, "docs", "validation", "demonstration-results.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out))
    print("\n".join(out))


if __name__ == "__main__":
    main()
