# NatureMask Studio

Local Windows web application that analyses the acoustic signature of a machine or power tool and
generates a **natural soundscape optimised to make that machine less perceptually prominent** —
while controlling how much sound is added.

> Masking adds sound. It never reduces the machine's sound power or level, it is not hearing
> protection, and it must not be used to hide alarms, warnings or speech that matters.

**Workflow:** import target noise → analyse → choose environment → optimise masking → preview & blind-test → export WAV / MATLAB.

## Quick start (Windows)

1. Requirements: **Python 3.11+** (tested 3.12.10; the pinned NumPy/pandas need 3.11). **Node.js LTS** is needed **once** to build the interface (tested 24.20).
2. Double-click **`start.bat`**. On first run it creates `.venv`, installs `requirements.txt`, builds the
   frontend, then starts the server and opens **http://127.0.0.1:8765**.
3. After installation everything works **offline**. No accounts, APIs or cloud services; recordings never leave the computer.

Close the console window to stop the app. Projects are stored in `data\projects\`.

## What it does

| Area | Capability |
|---|---|
| Inputs | MATLAB `.mat` v4–v7.3 (`sig`, `fs`, `t`, `dist`, `line`, calibration), WAV/FLAC, CSV/XLSX/XLS spectrum tables (column mapping, octave/third/narrowband detection, Lp **or Lw**, dB or dBA), manual LA/LZ/LC with labelled template spectra, interactive spectral editor (1/1, 1/3, continuous; tones; uncertainty), synthetic demo machines |
| Calibration | Pa, digital + factor k, digital + reference LAeq, or uncalibrated (relative dB only — no SPL is ever fabricated) |
| Sound power | Lw → Lp at the listener: `Lp = Lw + DI − 10·log10(Ω r²)` (free / hemispherical), optional ISO 9613-1 air absorption |
| Analysis | LAeq/LZeq/LCeq, LAFmax, L10/L50/L90, octave & third-octave (IEC 61260-1 base-10), Welch PSD, spectrogram, tonal screening (TNR/PR), temporal class, masking-difficulty indicator |
| Soundscapes | 16 procedural modules (birds with song grammar, wind, leaves, grass, stream, waterfall, rain, drips, waves, crickets with Dolbear's law, night insects, cicadas, frogs, owl, woodpecker, ambience); 12 presets; season/time/weather; deterministic seeds; chunked rendering; seamless loops; slow adaptation |
| Masking | NM-PSM v1 estimator (power-spectrum model, ERB roex filters); constrained optimisation `J = w1·ML + w2·AL + w3·UN` (all dB) with 5 objectives, level caps, Pareto sweep, infeasibility reporting |
| Evaluation | From the actual rendered audio: spectra of machine/soundscape/mix, ΔLA, masker-to-target ratio per band, masking margins, prominence over time |
| Listening | Three sample-aligned streams with instant switching; blind "can you hear the machine?" test with chance probability |
| Export | WAV PCM16/24/float32, MATLAB `.mat` (`sig, fs, t, duration, channels, L_Aeq, L_Zeq, f_oct, Lp_oct, f_third, Lp_third, f_psd, PSD, metadata`), CSV spectra, JSON spec, HTML report — all re-read and validated |

## Repository

```
.claude/skills/acoustics-sound-masking/   Claude Code skill: research, equations, algorithms, validation (Phase 1)
backend/app/                              FastAPI app: acoustics, psychoacoustics, dsp, synthesis, optimization, exports, storage, api
frontend/src/                             React + TypeScript + Tailwind + Plotly UI (pages, components, charts, audio)
tests/unit, tests/integration,            pytest suites; tests/ui = Edge/Playwright walkthrough;
tests/acoustic_validation                 MATLAB verification script
examples/                                 synthetic sample noise, demonstration runner, sample MAT export
docs/                                     research, architecture, API, algorithms, user guide, validation, limitations
start.bat, requirements.txt
```

## Tests

```bat
.venv\Scripts\python.exe -m pytest -q tests
python .claude\skills\acoustics-sound-masking\scripts\reference_impl.py --selftest
.venv\Scripts\python.exe examples\run_demonstrations.py
```
Status 2026-10-20: **102 pytest tests pass**, 42/42 skill reference checks, browser walkthrough in Edge with 0
console errors, MAT export verified with MATLAB R2021b. See `docs/validation/`.

## Documentation

- User guide — `docs/user-guide/user-guide.md`
- Acoustic methodology — `docs/algorithms/acoustic-methodology.md` (and the skill)
- Architecture & API — `docs/architecture/architecture.md`, `docs/architecture/api.md` (live OpenAPI at `/docs`)
- Validation — `docs/validation/` · Limitations & roadmap — `docs/limitations-and-roadmap.md`
- Phase 1 research report — `docs/research/technical-research-report.md`
