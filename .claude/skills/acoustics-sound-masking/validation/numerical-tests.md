# Numerical Test Plan

Status legend: implemented tests live in `NatureMask-Studio/tests/`; the skill's own reference
checks run with `python scripts/reference_impl.py --selftest` (42 checks, all PASS on 2026-10-20).

## Acoustic calculations
| ID | Test | Expected | Tolerance |
|---|---|---|---|
| A1 | RMS of 1 Pa-peak sine | 0.7071 Pa → 90.97 dB | 0.01 dB |
| A2 | Energy sum 80⊕80, 80⊕70, 10×60 | 83.01, 80.41, 70.00 | 0.01 |
| A3 | A-weighting at exact base-10 freqs vs IEC 61672-1 nominal table | table | 0.1 dB |
| A4 | Time-domain A filter (bilinear) vs analytic, 20 Hz–10 kHz | analytic | 0.3 dB (fs=48k) |
| A5 | Octave/third band edges & counts | 10 / 31 bands | exact |
| A6 | Third-octave integration of white noise | 30 + 10log10(BW) | 0.3 dB |
| A7 | Thirds→octave energy sum | 3×60 → 64.77 | 0.01 |
| A8 | Welch PSD Parseval | Σ G Δf = var | 3 % |
| A9 | Calibration: 1 kHz tone scaled by k=1/x_rms reads 94.0 dB | 93.98 | 0.05 |
| A10 | Uncalibrated input never yields SPL fields | absent / null | — |

## DSP
FFT amplitude of bin-centred sine; STFT inverse reconstruction (istft error < −100 dB);
resample_poly 44.1↔48 kHz preserves a 1 kHz tone level (±0.05 dB) and attenuates > 0.5 fs by
> 60 dB; clipping guard (peak ≤ −1 dBFS after normalisation); WAV PCM16/24/float32 round-trip
(error ≤ 1 LSB); MAT v5 and v7.3 round-trip.

## Generative audio
No NaN/Inf; deterministic (same seed ⇒ identical samples; different seed ⇒ different);
chunk-boundary continuity (chunked render == one-shot render, max abs diff < 1e-6); event
scheduler mean rate within ±10 % of λ over 10 min (Poisson); bird syllable frequencies stay in
configured range; long render (5 min) memory bounded and stable RMS (drift < 3 dB between first
and last minute for stationary presets); spectral target of shaped noise within ±1 dB per
third-octave (500 Hz–8 kHz).

## Masking model
| ID | Case | Expected |
|---|---|---|
| M1 | Synthetic tone 1 kHz at masker+K | d ≈ 0 dB at 1 kHz band |
| M2 | Broadband target at threshold (d_b = 0), masker raised +10 dB | all d_b ≈ −10 dB (where masker ≫ Tq) |
| M3 | Intermittent target (on/off) | PI(t) high in on-frames, low in off-frames |
| M4 | Mixed tonal + broadband target | tonal band dominates PI |
| M5 | Different masker spectra (pink vs HF insects) vs LF tone | pink lowers d at LF; insects don't |
| M6 | Max SPL constraint | optimizer respects L_A,masker ≤ limit |
| M7 | Unachievable target (strong 63 Hz tone, tight limit) | infeasible report lists 63 Hz band |
| M8 | Monotonicity: more masker gain ⇒ PI non-increasing | yes |

## Integration
Import spectrum → preset → generate → analyse → preview streams → export WAV & MAT → reload →
check sig/fs/t shapes, metadata domain, L_Aeq consistency (re-analysis within 0.1 dB).
MATLAB R2021b `load` of exported .mat (performed when MATLAB is available; `matlab -batch`).

## Not covered by numerical tests (needs listening tests)
Perceived masking, naturalness, pleasantness, fatigue — see reference-cases.md §Listening protocol.
