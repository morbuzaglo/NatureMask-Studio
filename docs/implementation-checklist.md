# Implementation Checklist

Status: ✅ done & tested · 🟡 partial · ⬜ not started. Updated at each milestone.

## Milestone 1 — Research & Skill ✅
- ✅ Skill `acoustics-sound-masking` (references, algorithms, validation)
- ✅ `reference_impl.py` 42/42 checks
- ✅ Phase 1 research report (`docs/research/technical-research-report.md`)

## Milestone 2 — Core numerical engine ✅
- ✅ SPL, energy sums, A/C/Z weighting (analytic + linear-phase FIR; bilinear IIR error documented)
- ✅ Fast/Slow time weighting, Leq, Lmax, L10/L50/L90
- ✅ Octave / third-octave bands (IEC 61260-1 base-10), PSD↔band conversions, octave↔third
- ✅ Lw → Lp at listener (free / hemispherical), ISO 9613-1 air absorption
- ✅ Welch PSD, spectrogram, tonal screening (TNR/PR), temporal classification
- ✅ ERB/Bark/roex, NM-PSM v1 masking estimator
- ✅ Importers: MAT v5/v7.3, WAV, CSV/XLSX/XLS with detection, cleaning, A-weight removal
- Tests: `tests/unit` 42 passed (2026-10-20)

## Milestone 3 — Generative environmental audio ✅
- ✅ Block-based deterministic core (1 s blocks, per-block seeds, carried filter/oscillator state, event tails)
- ✅ 16 modules: wind, leaves, grass, stream, waterfall, rain, drips, waves, birds (5 species-like profiles,
  Markov song grammar), woodpecker, owl, crickets (Dolbear temperature law), night insects, cicadas, frogs, ambience
- ✅ 12 presets incl. Custom; season / time-of-day / weather modifiers
- ✅ Scene mixer with bed EQ (linear-phase FIR) and slow adaptation curve; seamless loop crossfade
- ✅ Synthetic target from spectrum (+ tones, stationary/intermittent/varying), demo machines (synthetic)
- ✅ QA: spectrogram inspection found & fixed frog clicks (hard gating) and spiky rain transients
- Tests: 82 unit tests pass (chunk invariance bit-exact for all modules, seeds, presets, spectra, loop, 2-min stability)
## Milestone 4 — Masking optimization ✅
- ✅ Objective J = w1·ML + w2·AL + w3·UN (all in dB), 4 presets + custom weights, SLSQP multi-start
- ✅ Constraints: max masker L_A, max mix L_A; bounds on module offsets and bed EQ
- ✅ Infeasibility report (bands still audible, required masker level, LF warning)
- ✅ Pareto sweep (non-dominated set)
- ✅ Temporal adaptation curve (asymmetric smoothing, slew limit)
- ✅ Engine: targets from recordings / spectra / Lw (+distance) / LA-only templates / demos; analysis
  (levels, statistics, bands, PSD, spectrogram, tones, temporal class, difficulty heuristic)
- ✅ Generation to disk (memmap), common-gain previews, evaluation from rendered audio, exports module
- Finding: a dB² masking loss made every objective push the masker to its cap ("louder is better");
  fixed by expressing ML as RMS dB (documented in skill).
- Tests: 89 unit tests pass
## Milestone 5 — Frontend ⬜
## Milestone 6 — Integration & export ⬜
## Milestone 7 — Testing & refinement ⬜
