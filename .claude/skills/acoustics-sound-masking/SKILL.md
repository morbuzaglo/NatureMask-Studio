---
name: acoustics-sound-masking
description: Acoustics, psychoacoustic masking and natural-soundscape synthesis engineering — SPL/dBA/octave-band math, calibration (digital full-scale vs Pa), Welch PSD, ERB/Bark auditory filters, masked-threshold and detectability estimates, tonality screening, procedural nature-sound generators (birds, wind, insects, water, rain, leaves), masking optimization with level constraints, WAV/MAT export conventions, and the relevant ISO/IEC standards with their limits. Use for designing, implementing, reviewing or explaining sound masking, noise analysis or generative environmental audio.
when_to_use: Triggers on masking machine/tool noise, soundscape generation, octave or third-octave analysis, A-weighting, calibration to Pascals, ERB/Bark, masking thresholds, tonality/prominence, nature-sound synthesis, NatureMask Studio code, or questions about ISO 532/1996/9613/12913, IEC 61672/61260.
argument-hint: "[task, e.g. 'review the masking estimator' or 'third-octave levels of x.mat']"
metadata:
  version: 0.1.0
  research_snapshot: 2026-10-20
  reference_selftest: scripts/reference_impl.py --selftest (42 checks)
---

# Acoustics & Sound Masking

Skill dir `${CLAUDE_SKILL_DIR}`. Knowledge snapshot 2026-10-20. Every equation quoted here is
implemented and checked in `scripts/reference_impl.py` (`python … --selftest`).

## 1. Ground rules (always)

1. **Masking does not reduce sound.** Adding a masker never lowers source sound power or the
   physical level of the target. It can only reduce how *noticeable* the target is, and it usually
   *raises* the total level. Say so in any UI, report or answer.
2. **Never present an estimate as a measurement.** A spectrum reconstructed from a single dBA
   number, a machine template, or a synthetic target is labelled `ESTIMATED`/`SYNTHETIC`.
3. **No physical SPL without calibration.** Digital samples (dBFS) are not dB SPL. Report SPL only
   for signals in Pa or with an explicit calibration factor; otherwise use relative dB.
4. **Masking predictions are model estimates**, not guarantees of inaudibility. Distinguish
   *experimentally established* effects (power-spectrum model, critical-ratio data, soundscape
   listening tests) from *engineering heuristics* (our objective function, naturalness penalty).
   Never print "95 % of noise removed"-style numbers.
5. **Standards:** cite edition and scope; never reproduce text; never claim compliance unless the
   operative provisions were obtained and tested. ISO 9613 and ISO 12913 do **not** provide a
   masking-sound generation algorithm.
6. **Safety:** maskers must not be used to obscure alarms, warnings or speech that matters, and are
   not hearing protection. Respect configured level limits.

## 2. Decision tree

```
What do you need?
├─ Levels, weighting, energy sums ........ algorithms/spl-and-weighting.md
├─ Octave / 1/3-octave / PSD conversion .. algorithms/octave-bands.md, references/signal-processing.md
│     PSD (Pa²/Hz) ≠ FFT-bin level ≠ band SPL — integrate PSD over band edges
├─ Is my data calibrated? ................ references/measurement-calibration.md
├─ Have Lw (sound power) per band? ....... algorithms/sound-power-to-receiver.md (Lw → Lp at listener)
├─ Will masker X hide target Y? .......... algorithms/masking-models.md, references/auditory-masking.md
├─ Is the target tonal / prominent? ...... references/psychoacoustics.md §Tonality
├─ Generate a natural sound .............. references/synthesis-methods.md, algorithms/spectral-synthesis.md
├─ Choose levels / EQ for masking ........ algorithms/optimization.md
├─ Soundscape design & evidence .......... references/soundscape-design.md
├─ Which standard applies? ............... references/standards.md
├─ Tests & reference cases ............... validation/numerical-tests.md, validation/reference-cases.md
└─ What can't we claim? .................. validation/limitations.md
```

## 3. Core equations (cheat sheet; derivations in the references)

| Quantity | Formula | Check value |
|---|---|---|
| SPL | `Lp = 20 log10(p_rms / 20 µPa)` | 1 Pa rms → 93.98 dB |
| Energy sum | `L = 10 log10 Σ 10^(Li/10)` | 80 ⊕ 80 = 83.01; 80 ⊕ 70 = 80.41 |
| Band level from PSD | `Lb = 10 log10(∫_{f1}^{f2} G(f) df / p0²)` | 1 kHz 93.98 dB tone → 93.98 dB in its 1/3-oct band |
| A-weighting | IEC 61672-1 poles 20.6, 107.7, 737.9, 12194 Hz, +2.00 dB | A(1 kHz)=0, A(100 Hz)≈−19.1 |
| Band edges | `fm = 1000·G^(x/b)`, `G = 10^0.3`, edges `fm·G^(±1/2b)` | 125.89 Hz exact octave |
| ERB | `ERB = 24.7(4.37 f/1000 + 1)` Hz | 132.6 Hz at 1 kHz |
| ERB-number | `E = 21.4 log10(4.37 f/1000 + 1)` | 15.62 at 1 kHz |
| Bark | `z = 13 atan(0.00076 f) + 3.5 atan((f/7500)²)` | 8.51 at 1 kHz |
| Masked threshold (power-spectrum model) | `T_b = 10log10(10^((L_m,b + K)/10) + 10^(Tq/10))`, K ≈ −4 dB (tone in noise) | white noise 30 dB/Hz → 47.2 dB at 1 kHz |
| Air absorption | ISO 9613-1 formula | 5.0 dB/km at 1 kHz, 20 °C/70 % RH |

## 4. Masking workflow (what NatureMask Studio implements)

1. **Target characterisation:** Lw spectrum? → Lp at listener (r, Ω, DI); calibrated? → Pa; Welch PSD → 1/3-octave + ERB-band levels,
   tonal peaks (TNR/PR screening), short-time levels (125 ms) for temporal variability.
2. **Masker candidates:** long-term ERB-band spectra of each nature module (rendered excerpt).
3. **Estimator:** per ERB band, target filter level vs masked threshold of the masker → margin
   `d_b = L_t,b − T_b` (dB). Positive = predicted audible in that band. Detectability index
   `d'_total = √Σ (10^(d_b/10))²` (multiband energy-detector combination, heuristic scaling).
4. **Optimize** module gains (+ smooth EQ) for objective
   `J = w1·MaskingLoss + w2·AddedLevelPenalty + w3·UnnaturalnessPenalty` subject to
   `L_A,masker ≤ max`, `L_A,combined ≤ max` (definitions: algorithms/optimization.md).
5. **Temporal adaptation:** slow attack/release (seconds) on band gains and event density.
6. **Report** margins, ΔL_A, masker-to-target ratio per band, with model labels; flag
   infeasible cases (e.g. strong low-frequency tones needing impractical masker levels).

## 5. Evidence labels used in this skill

`STANDARD` (cited standard, edition verified) · `PEER_REVIEWED` · `TEXTBOOK` ·
`ENGINEERING_HEURISTIC` (ours, documented, not validated by listening tests) · `UNVERIFIED`.

## 6. Files

references/: `fundamentals.md` · `standards.md` · `psychoacoustics.md` · `auditory-masking.md` ·
`soundscape-design.md` · `measurement-calibration.md` · `signal-processing.md` ·
`synthesis-methods.md` · `source-bibliography.md` · `existing-solutions.md`
algorithms/: `spl-and-weighting.md` · `octave-bands.md` · `sound-power-to-receiver.md` ·
`masking-models.md` · `spectral-synthesis.md` · `optimization.md`
validation/: `numerical-tests.md` · `reference-cases.md` · `limitations.md`
scripts/: `reference_impl.py` (all equations + 42-check self-test)
