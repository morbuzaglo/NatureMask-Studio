# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

NatureMask Studio: local, offline Windows web app that analyses a machine's noise and generates a natural
soundscape optimised to make it less perceptually prominent. Backend Python/FastAPI (`backend/app`),
frontend React + TypeScript + Vite + Tailwind 4 + Plotly (`frontend/`), served by the same server.

## Ground rules (from the project skill)
Load `.claude/skills/acoustics-sound-masking/SKILL.md` for any acoustics, masking, DSP or synthesis work.
- Masking never reduces the machine's sound; it adds sound. Never claim otherwise in UI/docs.
- No SPL without calibration: uncalibrated designs report relative dB only; MAT exports then contain
  `Lrel_*` and **no** `L_Aeq`/`Lp_*`.
- Model outputs (NM-PSM v1, prominence index) are engineering estimates — never convert them to
  percentages or "probability masked".
- Every target carries `domain` (PASCAL / DIGITAL_CALIBRATED / DIGITAL_UNCALIBRATED / SPECTRUM_ONLY) and
  `provenance` (MEASURED / ESTIMATED_* / SYNTHETIC); audio reconstructed from spectra is labelled synthetic.

## Commands (Windows; run from the repo root)
```bat
start.bat                                            :: one-time setup + run on http://127.0.0.1:8765 (falls back to 8766..8775)
.venv\Scripts\python.exe -m pytest -q tests          :: all tests (~4 min)
.venv\Scripts\python.exe -m pytest -q tests\unit\test_masking_model.py::test_M1_tone_at_threshold
.venv\Scripts\python.exe -m pytest -q tests -k "optimizer or prediction"
.venv\Scripts\python.exe .claude\skills\acoustics-sound-masking\scripts\reference_impl.py --selftest
.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8765   :: backend only
cd frontend && npm run dev                           :: Vite dev server :5173, proxies /api to :8765
cd frontend && npx tsc --noEmit -p . && npx vite build   :: typecheck + build into frontend/dist (served by FastAPI)
.venv\Scripts\python.exe tests\ui\ui_walkthrough.py  :: Edge/Playwright end-to-end walkthrough (needs a running server)
.venv\Scripts\python.exe examples\run_demonstrations.py   :: Examples 1-5 -> docs/validation/demonstration-results.md
matlab -batch "addpath('tests/acoustic_validation'); verify_mat_in_matlab('<file.mat>')"   :: MATLAB R2021b is installed
```
Node is installed at `C:\Program Files\nodejs` and may be missing from the Bash tool's PATH — prepend it.
Tests set `NATUREMASK_DATA_DIR` (default data dir is `data/`); integration tests use `data/_itest`.

## Architecture (big picture)
Request flow: `frontend/src/pages/*` → `services/api.ts` → `backend/app/api/routes.py` → `engine.py`
(targets + analysis) / `optimization/optimizer.py` / `generation.py` (render + evaluate) /
`exports/exporters.py`. Long work (generate, export) runs in `api/jobs.py` thread pool; UI polls `/api/jobs/{id}`.
Projects are plain files: `data/projects/<id>/{project.json, target.npz, render/, exports/}` (`storage/projects.py`).

Invariants that span several files — keep them when changing code:
- **Units follow the target.** Calibrated designs compute in Pa (ref 20 µPa); uncalibrated ones in the
  recording's full-scale units (ref 1.0). `engine.to_units` / `target_psd` produce the target in those units;
  the optimizer's `master_db` scales the scene into the same units.
- **Deterministic block synthesis.** `synthesis/core.Module` renders fixed 1 s blocks seeded by
  `derive_seed(seed, kind, block)` with carried filter state and an event tail buffer → chunked output is
  bit-identical to one-shot output and independent of total duration (tested for every module). Random
  processes must use their own seeded streams; lognormal modulators are energy-normalised.
- **Prediction = render.** The optimizer analyses each module (`scene.module_psd`) over exactly the window
  `[0, generation.analysis_window_s(duration))` that generation renders and `generation.evaluate` analyses.
  Breaking this reintroduces a past 7.5 dB predicted-vs-rendered error (`tests/acoustic_validation`).
- **Objective terms are all in dB** (`ML` = weighted RMS excess, `AL` = added L_A, `UN`); a dB² masking loss
  made every objective max out the level. Default cap: soundscape L_A ≤ machine L_A + 3 dB. In the API an
  explicitly sent `null` cap means "no cap" (`model_fields_set`), an omitted one uses project settings.
- **Common gain.** Preview WAVs and "relative" exports share one normalisation gain across target/masker/mix;
  `pa_per_full_scale` in MAT metadata restores physical units. Exported Leq values are time-domain integrals.
- **A-weighting** uses a linear-phase FIR from the IEC analytic response (`levels.weighting_fir`); the
  bilinear IIR (`weighting_sos`) is ~1.2 dB off at 10 kHz and kept only for reference.
- New sound module: subclass `Module`, implement `_block(k, rng)`, register in `synthesis/scene.MODULE_TYPES`,
  add to `synthesis/presets.PRESETS`, and (frontend) to `PARAMS` in `pages/Soundscape.tsx`.

## Repo notes
- Lives in OneDrive. `.venv`, `node_modules`, `frontend/dist`, `data/` are git-ignored.
- Write `.bat` files with the Write tool (not Bash heredocs — the shell turns `>NUL` into `>/dev/null`) and
  keep CRLF line endings; dry-run copies inside the repo with side-effect lines replaced by `echo`.
- Don't leave a test server on 8765 while the user may launch the app.
- Docs: `README.md`, `docs/` (user guide, architecture, API, methodology, validation, limitations). Update
  `docs/implementation-checklist.md` and commit at the end of each milestone.
