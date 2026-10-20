# NatureMask Studio — Phase 1 Technical Research Report

Date 2026-10-20. Knowledge base: `.claude/skills/acoustics-sound-masking/` (all equations
implemented in `scripts/reference_impl.py`, 42/42 self-checks pass).

## 1. Research question
*How can a realistic environmental soundscape reduce the perceptual detectability or prominence of
a specific tool without unnecessarily increasing overall SPL?*

**Answer in brief.** Energetic masking happens within auditory filters: a target component becomes
inaudible when the masker's power in the same auditory filter exceeds the target's by roughly
−K ≈ 4 dB (power-spectrum model, experimentally established for tones in noise). The *cheapest*
masker in level terms therefore puts energy only where the target is audible, shaped to the
target's spectrum (spectral matching), and is noise-like (noise masks tones better than tones mask
noise). Natural sounds can supply this energy only within their plausible spectral envelopes:
water/wind/leaves cover ~200 Hz–4 kHz well, insects 4–8 kHz, birds intermittently 1.5–8 kHz; few
natural sounds plausibly cover < 150 Hz. Beyond energetic masking, listening experiments show that
natural sounds (especially birdsong) raise pleasantness and can reduce perceived loudness/annoyance
of moderate, steady noise even without full masking (Jeon 2010; De Coensel 2011; Hao 2016) — this is
the *prominence-reduction* route, with high inter-listener variability.

**Established vs heuristic.** Established: power-spectrum model, ERB/critical-band widths, upward
spread, temporal masking ranges, tone/noise asymmetry, the soundscape listening-test findings cited.
Heuristic (ours): the multiband prominence index, the naturalness penalty, the objective weights.
No overlap formula guarantees inaudibility.

## 2. Comparison of masking approaches
| Approach | Mechanism | Level efficiency | Naturalness | Evidence | Use in app |
|---|---|---|---|---|---|
| Spectral overlap (broadband bed shaped to target) | energetic | high if well matched | medium (EQ can sound artificial) | PSM, myNoise practice | Strategy 1 (bed EQ constrained by smoothness) |
| Critical-band masking estimator | energetic, per ERB | — (analysis) | — | PSM (PR) | Strategy 2: NM-PSM v1 |
| Temporal adaptation | follows target level | saves level when target quiet | risk of pumping | forward masking 100–200 ms; adaptation heuristics | Strategy 3: slow attack/release |
| Perceptual blending (events, plausibility) | informational / attention | low level cost | high | soundscape studies (PR) | Strategy 4: event density, preset coherence |
| Minimum added exposure | constraint | — | — | regulatory logic | Strategy 5: hard L_A constraints + AL penalty |
| Plain pink/white noise masking (office systems) | energetic | medium | low | ISO 3382-3 context | not used (contrast only) |
| Louder nature loop | energetic | poor | medium | — | explicitly avoided |

## 3. Standards relevance summary
Direct: IEC 61672-1:2013 (weightings), IEC 61260-1:2014 (bands), ISO 532-1:2017 (loudness, optional
via MoSQITo), ISO/TS 20065:2022 + ECMA-418 (tonality concepts). Background: ISO 1996-1:2016/-2:2017,
ISO 226:2023, ISO 389-7. Spatial (future): ISO 9613-1:1993 (formula implemented & checked),
ISO 9613-2:2024. Evaluation framework: ISO 12913-1:2014, ISO/TS 12913-2:2018, ISO/TS 12913-3:2025.
Related only: ISO 3382-3:2022. Details: `references/standards.md`.

## 4. Engineering design specification (v1)
- Inputs: MAT (v5/v7 via scipy, v7.3 via h5py), WAV, XLSX/XLS/CSV tables, manual values,
  **sound power spectra Lw (octave/third-octave) converted to Lp at a listener distance r**,
  spectral editor. Every dataset carries `domain` and `provenance` (MEASURED / ESTIMATED / SYNTHETIC).
- Analysis: Welch PSD (Hann, 50 % overlap), 1/1 & 1/3-octave via PSD integration, ERB bands, A/C/Z
  levels, L_AF(t), L10/L50/L90, tonal peaks with TNR/PR screening, spectrogram.
- Generation: 48 kHz default (44.1 supported), stereo/mono, 10 s – 60 min, chunked 10 s blocks with
  carried state, seed-deterministic, optional seamless loop (crossfade of tail into head over 3 s),
  global gain normalisation to peak ≤ −1 dBFS.
- Masking: NM-PSM v1 on ERB bands, objective J (ML, AL, UN) with SLSQP and constraints; Pareto sweep.
- Exports: WAV PCM16/24/float32; MAT (v5 via scipy `savemat`, readable by MATLAB `load`) with
  `sig, fs, t, duration, channels, L_Aeq, L_Zeq, f_oct, Lp_oct, f_third, Lp_third, f_psd, PSD,
  metadata`; CSV spectra; JSON project; HTML report.
- Limits: masker L_A max (default target+3 dB), mix L_A max; warnings ≥ 80 dBA (calibrated).

## 5. DSP & synthesis architecture
```
Target input ──► Importers ──► Signal/Spectrum model (domain, provenance)
                                  │
                                  ▼
                       Analysis (PSD, bands, ERB, tonal, temporal)
                                  │
Preset ─► Scene graph (modules: wind, leaves, stream, rain, waves, birds, insects, frogs, ambience)
                │  per-module long-term spectra (cached analysis renders)
                ▼
        Masking optimizer (NM-PSM v1 + J + constraints) ──► module gains, bed EQ, adaptation curve
                │
                ▼
        Chunked renderer (seeded RNG per module, stateful filters, event timeline, spatializer,
        bed EQ FIR, global gain) ──► audio (float32) ──► verification analysis ──► exports
```
Backend: Python 3.12, FastAPI, NumPy/SciPy, soundfile, h5py, openpyxl/xlrd, pandas; jobs run in a
thread pool with progress polling; projects stored as JSON + audio in `data/projects/<id>/`.
Frontend: React + TypeScript (Vite), Tailwind, Plotly.js, Web Audio API for A/B preview.

## 6. Test & validation strategy
Unit tests per `validation/numerical-tests.md` (acoustics, DSP, generators, masking), integration
test of the full workflow incl. WAV/MAT reload, MATLAB `load` check via `matlab -batch` when
available, plus a documented listening-test protocol (`validation/reference-cases.md`). Psycho-
acoustic validity is **not** claimed from unit tests.
